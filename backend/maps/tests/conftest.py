"""Shared test helpers for the map backend. No real map data: each test writes a tiny pack."""

import pytest
from fastapi.testclient import TestClient
from pmtiles.tile import Compression, TileType, zxy_to_tileid
from pmtiles.writer import write

from server.main import app


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
def client():
    return TestClient(app)
