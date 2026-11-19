"""Trails, roads and streams as lines, rasterized onto a Window.

Two steps, so the slow one runs once per region:

    extract(pbf, gpkg)          OSM extract (e.g. Geofabrik new-york-latest.osm.pbf)
                                -> one GeoPackage of classified lines, WGS84
    extract_nhd(nhd, gpkg)      USGS NHD state GeoPackage -> stream lines, same schema
    masks(sources, window)      lines inside a window -> trail/road/stream masks

Trails and roads come from OSM (ODbL: "(c) OpenStreetMap contributors").
Streams can come from OSM or from NHD (US public domain). OSM streams are
patchy in New York; NHD maps them from 1:24,000 sources statewide. Mixing
sources is fine for one region, but compare completeness before pooling
regions built from different sources.

Which OSM tags count as trail, road or stream is a modeling choice, written
down in CLASSES. ``highway=track`` (forest and farm tracks) is a road here;
moving it to trail changes what "near a trail" means.
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import numpy as np
import osmium
import pyogrio
import shapely
from affine import Affine
from rasterio.features import rasterize

from spm.geodata.dem import window_lonlat_bounds
from spm.geodata.grid import Window

# class -> (OSM key, values)
# Bump when CLASSES or the mask rules change: cached stacks built under an older
# schema are then rebuilt instead of being silently reused (geodata.build).
SCHEMA = 1

CLASSES = {
    "trail": ("highway", {"path", "footway", "bridleway", "steps"}),
    "road": (
        "highway",
        {
            "motorway",
            "motorway_link",
            "trunk",
            "trunk_link",
            "primary",
            "primary_link",
            "secondary",
            "secondary_link",
            "tertiary",
            "tertiary_link",
            "unclassified",
            "residential",
            "service",
            "track",
        },
    ),
    "stream": ("waterway", {"stream", "river"}),
}
LAYER = "lines"

# NHD flowline FType kept as "stream": 460 StreamRiver. Left out: 558
# ArtificialPath (centre lines through lakes and wide rivers), 336 CanalDitch,
# 334 Connector, 566 Coastline, 428 Pipeline, 420 UndergroundConduit.
# FCode (46006 perennial, 46003 intermittent, 46000 unspecified) is kept in
# ``tag`` so perennial and intermittent streams can be split later.
NHD_LAYER = "NHDFlowline"
NHD_STREAM_FTYPES = (460,)


def classify(tags) -> str | None:
    """Line class for a way's tags, or None if it is none of them."""
    for cls, (key, values) in CLASSES.items():
        if tags.get(key) in values:
            return cls
    return None


def extract(pbf: Path, gpkg: Path) -> int:
    """Write every trail, road and stream way in ``pbf`` to ``gpkg``; return the count."""
    keys = sorted({key for key, _ in CLASSES.values()})
    wkb = osmium.geom.WKBFactory()
    ids, classes, tags, geoms = [], [], [], []
    fp = osmium.FileProcessor(str(pbf)).with_locations().with_filter(osmium.filter.KeyFilter(*keys))
    for obj in fp:
        if not obj.is_way():
            continue
        cls = classify(obj.tags)
        if cls is None:
            continue
        try:
            geom = shapely.from_wkb(wkb.create_linestring(obj))
        except (osmium.InvalidLocationError, RuntimeError):
            continue  # nodes cut off at the extract edge, or fewer than 2 nodes
        key = CLASSES[cls][0]
        ids.append(obj.id)
        classes.append(cls)
        tags.append(obj.tags.get(key))
        geoms.append(geom)
    gdf = gpd.GeoDataFrame({"src_id": ids, "cls": classes, "tag": tags}, geometry=geoms, crs=4326)
    return _write(gdf, gpkg)


def extract_nhd(nhd_gpkg: Path, gpkg: Path, exclude_fcodes: tuple[int, ...] = ()) -> int:
    """Write the NHD StreamRiver flowlines in ``nhd_gpkg`` to ``gpkg``; return the count.

    ``nhd_gpkg`` is an unzipped USGS state GeoPackage (NHD_H_<State>_State_GPKG.gpkg).
    Geometry is reduced to 2-D (NHD carries Z and M) and reprojected from NAD83 to WGS84.
    ``exclude_fcodes`` drops hydrography classes, e.g. 46007 (ephemeral washes).
    """
    ftypes = ", ".join(str(f) for f in NHD_STREAM_FTYPES)
    where = f"ftype IN ({ftypes})"
    if exclude_fcodes:
        where += " AND fcode NOT IN (" + ", ".join(str(c) for c in exclude_fcodes) + ")"
    src = gpd.read_file(
        nhd_gpkg,
        layer=NHD_LAYER,
        columns=["permanent_identifier", "fcode"],
        where=where,
    )
    geoms = shapely.force_2d(src.geometry.values)
    gdf = gpd.GeoDataFrame(
        {
            "src_id": src["permanent_identifier"].astype(str),
            "cls": "stream",
            "tag": src["fcode"].astype(str),
        },
        geometry=geoms,
        crs=4269,
    ).to_crs(4326)
    return _write(gdf, gpkg)


def _write(gdf: gpd.GeoDataFrame, gpkg: Path) -> int:
    gpkg.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_file(gpkg, layer=LAYER, driver="GPKG")
    return len(gdf)


def read_lines(gpkg: Path, window: Window) -> gpd.GeoDataFrame:
    """Lines touching the window, reprojected to the window CRS."""
    gdf = gpd.read_file(gpkg, layer=LAYER, bbox=window_lonlat_bounds(window))
    return gdf.to_crs(window.epsg)


def file_bounds(gpkg: Path) -> tuple[float, float, float, float]:
    """(lon_min, lat_min, lon_max, lat_max) of a lines GeoPackage, from its metadata."""
    return tuple(pyogrio.read_info(gpkg, layer=LAYER)["total_bounds"])


def masks(sources: Path | dict[str, Path | list[Path]], window: Window) -> dict[str, np.ndarray]:
    """``{class}_mask`` layer per class: True in every cell a line of that class touches.

    ``sources`` is one GeoPackage for every class, or a class -> GeoPackage(s) map
    (e.g. trails and roads from OSM, streams from NHD; several files per class
    when a window spans regions).
    """
    if not isinstance(sources, dict):
        sources = {cls: sources for cls in CLASSES}
    sources = {k: v if isinstance(v, list) else [v] for k, v in sources.items()}
    read = {p: read_lines(p, window) for paths in sources.values() for p in paths}
    transform = Affine(*window.affine())
    out = {}
    for cls in CLASSES:
        geoms = [g for p in sources[cls] for g in read[p].geometry[read[p]["cls"] == cls]]
        if len(geoms):
            m = rasterize(
                ((g, 1) for g in geoms),
                out_shape=window.shape,
                transform=transform,
                all_touched=True,
                dtype="uint8",
            )
        else:
            m = np.zeros(window.shape, dtype="uint8")
        out[f"{cls}_mask"] = m.astype(bool)
    return out
