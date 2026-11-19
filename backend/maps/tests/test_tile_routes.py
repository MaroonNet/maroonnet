"""The tile routes: /tiles/basemap/{z}/{x}/{y} and /tiles/terrain/{z}/{x}/{y}."""

import gzip

from pmtiles.tile import Compression, TileType

from maps.routes import BASEMAP_SETTING, TERRAIN_SETTING

VECTOR_TILE = b"a vector tile"
TERRAIN_TILE = b"RIFF....WEBP a terrain tile"


def test_basemap_tile_inside_the_pack(make_pack, client, monkeypatch):
    monkeypatch.setenv(BASEMAP_SETTING, make_pack({(10, 213, 388): gzip.compress(VECTOR_TILE)}))
    response = client.get("/tiles/basemap/10/213/388")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/vnd.mapbox-vector-tile"
    assert response.headers["content-encoding"] == "gzip"
    # The test client unpacks gzip as a browser would, so this checks the header is honest.
    assert response.content == VECTOR_TILE


def test_basemap_tile_outside_the_pack(make_pack, client, monkeypatch):
    monkeypatch.setenv(BASEMAP_SETTING, make_pack({(10, 213, 388): gzip.compress(VECTOR_TILE)}))
    assert client.get("/tiles/basemap/10/100/100").status_code == 404


def test_terrain_tile_is_served_uncompressed(make_pack, client, monkeypatch):
    path = make_pack({(12, 852, 1554): TERRAIN_TILE}, TileType.WEBP, Compression.NONE)
    monkeypatch.setenv(TERRAIN_SETTING, path)
    response = client.get("/tiles/terrain/12/852/1554")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/webp"
    assert "content-encoding" not in response.headers
    assert response.content == TERRAIN_TILE


def test_terrain_tile_outside_the_pack(make_pack, client, monkeypatch):
    path = make_pack({(12, 852, 1554): TERRAIN_TILE}, TileType.WEBP, Compression.NONE)
    monkeypatch.setenv(TERRAIN_SETTING, path)
    assert client.get("/tiles/terrain/12/0/0").status_code == 404


def test_column_beyond_the_edge_of_the_world(make_pack, client, monkeypatch):
    monkeypatch.setenv(BASEMAP_SETTING, make_pack({(10, 213, 388): gzip.compress(VECTOR_TILE)}))
    # Zoom 2 has columns 0 to 3 only.
    assert client.get("/tiles/basemap/2/4/0").status_code == 404


def test_pack_not_configured(client, monkeypatch):
    monkeypatch.delenv(BASEMAP_SETTING, raising=False)
    response = client.get("/tiles/basemap/10/213/388")
    assert response.status_code == 503
    assert BASEMAP_SETTING in response.json()["detail"]


def test_pack_file_missing(tmp_path, client, monkeypatch):
    monkeypatch.setenv(BASEMAP_SETTING, str(tmp_path / "gone.pmtiles"))
    assert client.get("/tiles/basemap/10/213/388").status_code == 503


def test_setting_that_is_not_a_pack(tmp_path, client, monkeypatch):
    junk = tmp_path / "junk.pmtiles"
    junk.write_bytes(b"not a pack")
    for path in [junk, tmp_path]:  # a file that is not a pack, and a folder
        monkeypatch.setenv(BASEMAP_SETTING, str(path))
        assert client.get("/tiles/basemap/10/213/388").status_code == 503, path
