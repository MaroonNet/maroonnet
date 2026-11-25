"""The installed packs list: GET /api/maps/packs."""

from maps.installed import scan

TERRAIN_TILE = b"RIFF....WEBP a terrain tile"

BRAINARD_BOX = [-105.70, 40.02, -105.55, 40.12]


def test_with_no_pack_installed_the_list_is_empty(client):
    response = client.get("/api/maps/packs")

    assert response.status_code == 200
    assert response.json() == []


def test_each_installed_pack_is_listed_as_its_pack_json_says(install_pack, client):
    install_pack("state/CO/terrain", {(12, 852, 1554): TERRAIN_TILE})
    install_pack("mission/brainard", {(14, 3381, 6200): TERRAIN_TILE}, name="Brainard Lake",
                 area=[BRAINARD_BOX], min_zoom=13, max_zoom=16, data_date="2026-10-01", bytes=1200)

    response = client.get("/api/maps/packs")

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": "mission/brainard", "kind": "mission", "contents": "terrain", "name": "Brainard Lake",
            "area": [BRAINARD_BOX], "min_zoom": 13, "max_zoom": 16,
            "data_date": "2026-10-01", "downloaded": "2026-10-24", "bytes": 1200, "status": "complete",
        },
        {
            "id": "state/CO/terrain", "kind": "state", "contents": "terrain", "name": "Colorado",
            "area": [[-109.06, 36.99, -102.04, 41.00]], "min_zoom": 0, "max_zoom": 12,
            "data_date": None, "downloaded": "2026-10-24", "bytes": 683000000, "status": "complete",
        },
    ]


def test_a_partial_pack_is_listed_as_partial(data_dir, write_pack_json, client):
    maps =data_dir / "maps"
    write_pack_json(maps / "state/CO/basemap", contents="basemap", status="partial")
    scan(maps)

    response = client.get("/api/maps/packs")

    assert [(pack["id"], pack["status"]) for pack in response.json()] == [("state/CO/basemap", "partial")]
