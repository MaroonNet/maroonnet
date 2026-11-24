"""The tile routes: /tiles/basemap/{z}/{x}/{y} and /tiles/terrain/{z}/{x}/{y}."""

import gzip

VECTOR_TILE = b"a vector tile"
TERRAIN_TILE = b"RIFF....WEBP a terrain tile"


def test_basemap_tile_inside_the_pack(install_pack, client):
    install_pack("state/CO/basemap", {(10, 213, 388): gzip.compress(VECTOR_TILE)})
    response = client.get("/tiles/basemap/10/213/388")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/vnd.mapbox-vector-tile"
    assert response.headers["content-encoding"] == "gzip"
    # The test client unpacks gzip as a browser would, so this checks the header is honest.
    assert response.content == VECTOR_TILE


def test_basemap_tile_outside_the_pack(install_pack, client):
    install_pack("state/CO/basemap", {(10, 213, 388): gzip.compress(VECTOR_TILE)})
    assert client.get("/tiles/basemap/10/100/100").status_code == 404


def test_terrain_tile_is_served_uncompressed(install_pack, client):
    install_pack("state/CO/terrain", {(12, 852, 1554): TERRAIN_TILE})
    response = client.get("/tiles/terrain/12/852/1554")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/webp"
    assert "content-encoding" not in response.headers
    assert response.content == TERRAIN_TILE


def test_terrain_tile_outside_the_pack(install_pack, client):
    install_pack("state/CO/terrain", {(12, 852, 1554): TERRAIN_TILE})
    assert client.get("/tiles/terrain/12/0/0").status_code == 404


def test_column_beyond_the_edge_of_the_world(install_pack, client):
    install_pack("state/CO/basemap", {(10, 213, 388): gzip.compress(VECTOR_TILE)})
    # Zoom 2 has columns 0 to 3 only.
    assert client.get("/tiles/basemap/2/4/0").status_code == 404


def test_no_pack_installed(client):
    response = client.get("/tiles/basemap/10/213/388")
    assert response.status_code == 404
    assert response.json()["detail"] == "no installed pack has this tile"


def test_each_state_basemap_answers_for_its_own_tiles(install_pack, client):
    install_pack("state/AZ/basemap", {(10, 193, 411): gzip.compress(b"arizona")})
    install_pack("state/CO/basemap", {(10, 213, 388): gzip.compress(b"colorado")})
    assert client.get("/tiles/basemap/10/193/411").content == b"arizona"
    assert client.get("/tiles/basemap/10/213/388").content == b"colorado"


def test_the_newer_basemap_answers_a_tile_two_states_share(install_pack, client):
    # A tile on the state line is in both packs.
    install_pack("state/AZ/basemap", {(6, 12, 25): gzip.compress(b"older")}, data_date="2026-10-23")
    install_pack("state/CO/basemap", {(6, 12, 25): gzip.compress(b"newer")}, data_date="2026-11-20")
    assert client.get("/tiles/basemap/6/12/25").content == b"newer"


def test_terrain_comes_from_a_mission_pack_first_then_the_state_pack(install_pack, client):
    install_pack("state/CO/terrain", {(12, 852, 1554): b"state 12", (10, 213, 388): b"state 10"})
    install_pack("mission/brainard-lake", {(14, 3409, 6217): b"mission 14", (12, 852, 1554): b"mission 12"},
                 min_zoom=12, max_zoom=14)
    assert client.get("/tiles/terrain/14/3409/6217").content == b"mission 14"
    assert client.get("/tiles/terrain/12/852/1554").content == b"mission 12"  # both have it
    assert client.get("/tiles/terrain/10/213/388").content == b"state 10"     # only the state pack has it


def test_a_basemap_pack_never_answers_a_terrain_request(install_pack, client):
    install_pack("state/CO/basemap", {(10, 213, 388): gzip.compress(VECTOR_TILE)})
    assert client.get("/tiles/terrain/10/213/388").status_code == 404


def test_a_partial_pack_is_not_asked(install_pack, write_pack_json, data_dir, client):
    install_pack("state/CO/terrain", {(10, 213, 388): b"state 10"})
    write_pack_json(data_dir / "maps/mission/half-done", kind="mission", status="partial")
    install_pack("state/CO/basemap", {(0, 0, 0): gzip.compress(VECTOR_TILE)})  # finds the packs again
    assert client.get("/tiles/terrain/10/213/388").content == b"state 10"
