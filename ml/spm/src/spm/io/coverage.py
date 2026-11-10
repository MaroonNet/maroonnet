"""Searched areas as a per-cell POD raster on a Window.

Input is what (P)MP will have: sector polygons as GeoJSON (WGS84), each with
a ``pod`` property in [0, 1] saying how likely that search would have found
the subject had they been there. Overlapping sectors combine as independent
searches (models.update.combine_pod). A POD raster already on disk (GeoTIFF,
any CRS) is reprojected onto the window instead.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np
import rasterio
import shapely
from affine import Affine
from pyproj import Transformer
from rasterio.features import rasterize
from rasterio.warp import Resampling, reproject

from spm.geodata.grid import Window
from spm.models.update import combine_pod

log = logging.getLogger(__name__)


def pod_from_geojson(source: Path | dict, window: Window) -> np.ndarray:
    """POD per window cell from a FeatureCollection of polygons with a ``pod`` property."""
    doc = json.loads(Path(source).read_text()) if not isinstance(source, dict) else source
    features = doc.get("features", [doc] if doc.get("type") == "Feature" else [])
    to_win = Transformer.from_crs(4326, window.epsg, always_xy=True).transform
    transform = Affine(*window.affine())
    layers = []
    skipped = []
    for f in features:
        props = f.get("properties") or {}
        if "pod" not in props or f.get("geometry") is None:
            skipped.append(str(props.get("id", f.get("id", "?"))))
            continue
        pod = float(props["pod"])
        if not 0.0 <= pod <= 1.0:
            raise ValueError(f"pod {pod} not in [0, 1] (feature {props.get('id', '?')})")
        geom = shapely.transform(
            shapely.geometry.shape(f["geometry"]),
            lambda xy: np.column_stack(to_win(xy[:, 0], xy[:, 1])),
        )
        mask = rasterize(
            [(geom, 1)], out_shape=window.shape, transform=transform, dtype="uint8"
        ).astype(bool)
        layers.append(np.where(mask, pod, 0.0))
    if skipped:
        log.warning(
            "%d of %d searched-area features ignored (no 'pod' property or no geometry): %s",
            len(skipped),
            len(features),
            ", ".join(skipped),
        )
    if not layers:
        return np.zeros(window.shape)
    return combine_pod(layers)


def pod_from_raster(path: Path, window: Window) -> np.ndarray:
    """Band 1 of a POD GeoTIFF resampled (nearest) onto the window; nodata and NaN become 0."""
    out = np.zeros(window.shape, dtype=np.float32)
    with rasterio.open(path) as src:
        reproject(
            source=rasterio.band(src, 1),
            destination=out,
            src_nodata=src.nodata,
            dst_transform=Affine(*window.affine()),
            dst_crs=f"EPSG:{window.epsg}",
            dst_nodata=0.0,
            resampling=Resampling.nearest,
        )
    return np.nan_to_num(out.astype(float), nan=0.0)
