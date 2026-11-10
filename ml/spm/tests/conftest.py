"""Shared fixtures: a synthetic 3DEP-style tile and a hand-written OSM extract (no network)."""

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from spm.geodata import lines

LON, LAT = -74.5, 44.3  # inside 3DEP tile n45w075

OSM_XML = """<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
  <node id="1" lat="44.3" lon="-74.506"/>
  <node id="2" lat="44.3" lon="-74.494"/>
  <node id="3" lat="44.296" lon="-74.506"/>
  <node id="4" lat="44.296" lon="-74.494"/>
  <node id="5" lat="44.304" lon="-74.5"/>
  <node id="6" lat="44.296" lon="-74.5"/>
  <node id="7" lat="44.301" lon="-74.501"/>
  <node id="8" lat="44.301" lon="-74.500"/>
  <way id="10"><nd ref="1"/><nd ref="2"/><tag k="highway" v="path"/></way>
  <way id="11"><nd ref="3"/><nd ref="4"/><tag k="highway" v="track"/></way>
  <way id="12"><nd ref="5"/><nd ref="6"/><tag k="waterway" v="stream"/></way>
  <way id="13"><nd ref="7"/><nd ref="8"/><tag k="building" v="yes"/></way>
</osm>
"""


@pytest.fixture
def tile_dir(tmp_path):
    """A small NAD83 tile named like 3DEP: elevation = 1000 m + 10 m per 0.001 deg east."""
    d = tmp_path / "tiles"
    d.mkdir()
    step = 0.0001
    lon0, lat0, n = -74.6, 44.4, 2000
    lons = lon0 + (np.arange(n) + 0.5) * step
    z = np.tile(1000.0 + 10_000.0 * (lons - LON), (n, 1)).astype("float32")
    with rasterio.open(
        d / "USGS_13_n45w075.tif",
        "w",
        driver="GTiff",
        width=n,
        height=n,
        count=1,
        dtype="float32",
        crs="EPSG:4269",
        transform=from_origin(lon0, lat0, step, step),
        nodata=-999999.0,
    ) as dst:
        dst.write(z, 1)
    return d


@pytest.fixture
def gpkg(tmp_path):
    osm = tmp_path / "test.osm"
    osm.write_text(OSM_XML)
    out = tmp_path / "lines.gpkg"
    assert lines.extract(osm, out) == 3  # building is ignored
    return out
