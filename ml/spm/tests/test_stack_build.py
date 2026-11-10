"""Stack builder on a synthetic elevation tile and a hand-written OSM file (no network)."""

import numpy as np
import pytest
from conftest import LAT, LON, OSM_XML

from spm.geodata import dem, lines
from spm.geodata.build import StackBuilder, window_for
from spm.geodata.grid import Window
from spm.schema import Case, LonLat


def test_tile_names():
    assert dem.tiles_for_bounds(-74.6, 44.2, -74.4, 44.4) == ["n45w075"]
    assert dem.tiles_for_bounds(-74.1, 43.9, -73.9, 44.1) == [
        "n44w075",
        "n44w074",
        "n45w075",
        "n45w074",
    ]


def test_read_dem_resamples_onto_window(tile_dir):
    win = Window.around(LON, LAT, side_m=1000, res=10)
    z = dem.read_dem(win, tile_dir)
    assert z.shape == win.shape and np.isfinite(z).all()
    r, c = win.rowcol(LON, LAT)
    assert abs(z[r, c] - 1000.0) < 2.0
    assert z[r, -1] > z[r, c] > z[r, 0]  # rises to the east


def test_extract_classifies_and_masks_follow_lines(gpkg):
    win = Window.around(LON, LAT, side_m=1000, res=10)
    m = lines.masks(gpkg, win)
    assert set(m) == {"trail_mask", "road_mask", "stream_mask"}
    r, c = win.rowcol(-74.5, 44.3)
    assert m["trail_mask"][r].sum() > 50  # east-west path through the centre row
    assert m["stream_mask"][:, c].sum() > 50  # north-south stream through the centre column
    assert m["road_mask"].any() and not m["road_mask"][r].any()


def test_builder_caches_and_reloads(tile_dir, gpkg, tmp_path):
    case = Case(case_id="t:1", source="t", ipp=None, find=LonLat(LON, LAT), category="hiker")
    win = window_for(case, side_m=1000, res=10)
    builder = StackBuilder(gpkg, tile_dir=tile_dir, cache_dir=tmp_path / "stacks")
    first = builder(case, win)
    assert len(list((tmp_path / "stacks").glob("*.npz"))) == 1
    again = builder(case, win)
    for k in first.layers:
        np.testing.assert_array_equal(first[k], again[k])
    assert again.source == first.source == builder.sources(win)[1]


@pytest.fixture
def nhd_gpkg(tmp_path):
    """A fake NHD state GeoPackage: one StreamRiver (kept) and one ArtificialPath (dropped)."""
    import geopandas as gpd
    from shapely.geometry import MultiLineString

    gdf = gpd.GeoDataFrame(
        {"permanent_identifier": ["a", "b"], "ftype": [460, 558], "fcode": [46003, 55800]},
        geometry=[
            MultiLineString([[(-74.503, 44.304, 0.0), (-74.503, 44.296, 0.0)]]),
            MultiLineString([[(-74.506, 44.302, 0.0), (-74.494, 44.302, 0.0)]]),
        ],
        crs=4269,
    )
    path = tmp_path / "nhd_state.gpkg"
    gdf.to_file(path, layer=lines.NHD_LAYER, driver="GPKG")
    return path


def test_nhd_streams_replace_osm_streams(nhd_gpkg, gpkg, tile_dir, tmp_path):
    out = tmp_path / "nhd_lines.gpkg"
    assert lines.extract_nhd(nhd_gpkg, out) == 1  # ArtificialPath left out
    win = Window.around(LON, LAT, side_m=1000, res=10)
    m = lines.masks({"trail": gpkg, "road": gpkg, "stream": out}, win)
    _, c_osm = win.rowcol(-74.5, 44.3)
    _, c_nhd = win.rowcol(-74.503, 44.3)
    assert m["stream_mask"][:, c_nhd].sum() > 50  # NHD stream column
    assert not m["stream_mask"][:, c_osm].any()  # OSM stream not used
    assert m["trail_mask"].any()  # trails still from OSM

    osm_only = StackBuilder(gpkg, tile_dir=tile_dir, cache_dir=tmp_path / "s")
    with_nhd = StackBuilder(gpkg, tile_dir=tile_dir, cache_dir=tmp_path / "s", streams_gpkg=out)
    # cache rebuilds when the stream source changes
    assert osm_only.sources(win)[1] != with_nhd.sources(win)[1]


def test_builder_uses_only_overlapping_region_files(gpkg, tile_dir, tmp_path):
    far_osm = tmp_path / "far.osm"
    far_osm.write_text(OSM_XML.replace('lon="-74.', 'lon="-111.').replace('lat="44.', 'lat="34.'))
    far = tmp_path / "far_lines.gpkg"
    lines.extract(far_osm, far)
    win = Window.around(LON, LAT, side_m=1000, res=10)
    one = StackBuilder(gpkg, tile_dir=tile_dir)
    both = StackBuilder([gpkg, far], tile_dir=tile_dir)
    assert both.sources(win)[1] == one.sources(win)[1]  # far region not mentioned
    per_class, _ = both.sources(win)
    assert per_class["trail"] == [gpkg]
    a, b = one(None, win), both(None, win)
    for k in a.layers:
        np.testing.assert_array_equal(a[k], b[k])


def test_region_stack_crops_identically(gpkg, tile_dir, tmp_path):
    builder = StackBuilder(gpkg, tile_dir=tile_dir, cache_dir=tmp_path / "c")
    region = builder.region((LON - 0.012, LAT - 0.01, LON + 0.012, LAT + 0.01), res=10)
    assert region.window.n * 10 >= 2000 and (tmp_path / "c" / "regions").exists()
    win = Window.around(LON, LAT, side_m=1000, res=10)
    cropped = builder.crop(win)
    assert cropped is not None and cropped.window == win
    direct = builder.build(win)
    for k in direct.layers:
        if k == "dem":  # bilinear resampling of a bigger raster rounds a little differently
            np.testing.assert_allclose(cropped[k], direct[k], atol=0.01)
        else:
            np.testing.assert_array_equal(cropped[k], direct[k])
    # a fresh builder finds the saved region on disk and crops without building
    again = StackBuilder(gpkg, tile_dir=tile_dir, cache_dir=tmp_path / "c")
    assert again.crop(win) is not None
    assert again.crop(Window.around(LON + 1.0, LAT, side_m=1000, res=10)) is None  # outside
    assert again.crop(Window.around(LON, LAT, side_m=1000, res=25)) is None  # other grid


def test_region_crop_downsamples_to_a_coarser_window(gpkg, tile_dir, tmp_path):
    builder = StackBuilder(gpkg, tile_dir=tile_dir, cache_dir=tmp_path / "c")
    builder.region((LON - 0.012, LAT - 0.01, LON + 0.012, LAT + 0.01), res=10)
    win = Window.around(LON, LAT, side_m=1000, res=20)  # 20 m cells on the 10 m region
    stack = builder.crop(win)
    assert stack is not None and stack["dem"].shape == win.shape
    fine = builder.crop(Window(win.epsg, win.x0, win.y0, 10.0, win.n * 2))
    np.testing.assert_allclose(
        stack["dem"], fine["dem"].reshape(win.n, 2, win.n, 2).mean(axis=(1, 3)), atol=0.01
    )
    assert stack["trail_mask"].sum() <= fine["trail_mask"].sum()
    assert stack["trail_mask"].any() == fine["trail_mask"].any()
