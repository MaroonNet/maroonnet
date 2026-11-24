"""Shared test helpers for the map backend. No real map data: each test writes a tiny pack."""

import pytest
from fastapi.testclient import TestClient
from pmtiles.tile import Compression, TileType, zxy_to_tileid
from pmtiles.writer import write

from maps.installed import folder_holds, installed, scan
from maps.pack_info import PackInfo, write_pack_info
from maps.tests.samples import COLORADO_TERRAIN
from server.main import app


@pytest.fixture(autouse=True)
def forget_installed_packs():
    """Empties the backend's list of installed packs after each test, so no test sees another's."""
    yield
    installed.clear()


@pytest.fixture
def make_pack(tmp_path):
    """Returns a function that writes a made-up pack and gives back its path.

    tiles maps (z, x, y) to the bytes stored for that tile, exactly as the pack will hold them.
    """

    def _make_pack(tiles, tile_type=TileType.MVT, compression=Compression.GZIP, name="test.pmtiles"):
        path = tmp_path / name
        with write(path) as writer:
            # A pack lists its tiles in tile-id order.
            for tile_id, data in sorted((zxy_to_tileid(*zxy), data) for zxy, data in tiles.items()):
                writer.write_tile(tile_id, data)
            writer.finalize({"tile_type": tile_type, "tile_compression": compression}, {})
        return str(path)

    return _make_pack


@pytest.fixture
def write_pack_json():
    """Returns a function that writes a valid pack.json into a folder, with any fields changed."""

    def _write_pack_json(folder, **changes):
        folder.mkdir(parents=True, exist_ok=True)
        write_pack_info(folder, PackInfo.model_validate({**COLORADO_TERRAIN, **changes}))

    return _write_pack_json


@pytest.fixture
def install_pack(data_dir, make_pack, write_pack_json):
    """Returns a function that puts a made-up pack in the maps folder and has the backend find it,
    as it does when it starts. The pack's id says what it is: "state/CO/terrain"."""

    def _install_pack(pack_id, tiles, **changes):
        maps = data_dir / "maps"
        kind, contents = folder_holds(pack_id)
        write_pack_json(maps / pack_id, kind=kind, contents=contents, file="map.pmtiles", **changes)
        if contents == "terrain":  # heights are WebP pictures, stored as they are
            tile_type, compression = TileType.WEBP, Compression.NONE
        else:
            tile_type, compression = TileType.MVT, Compression.GZIP
        make_pack(tiles, tile_type, compression, name=str(maps / pack_id / "map.pmtiles"))
        scan(maps)

    return _install_pack


@pytest.fixture
def client():
    return TestClient(app)
