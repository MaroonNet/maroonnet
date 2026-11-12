"""The style route and the files it points at: /maps/style.json, /maps/fonts/, /maps/sprites/."""

import json
import re

from pmtiles.tile import Compression, TileType

from maps.routes import TERRAIN_SETTING, is_asset_name

ORIGIN = "http://testserver"  # the address the test client sends its requests to


def get_style(client):
    response = client.get("/maps/style.json")
    assert response.status_code == 200
    return response.json()


def test_style_names_no_internet_addresses(client):
    text = json.dumps(get_style(client))
    addresses = re.findall(r"https?://[^\"\s]+", text)
    assert addresses, "the style should name the tile, font and icon sheet addresses"
    # Every address points back at the server the style came from.
    assert [a for a in addresses if not a.startswith(ORIGIN + "/")] == []


def test_every_layer_has_a_group_and_its_own_id(client):
    layers = get_style(client)["layers"]
    assert all(layer["metadata"]["group"] for layer in layers)
    ids = [layer["id"] for layer in layers]
    assert len(ids) == len(set(ids))


def test_every_font_file_loads(client):
    faces = get_style(client)["font-faces"]
    for files in faces.values():
        for file in files:
            response = client.get(file["url"].removeprefix(ORIGIN))
            assert response.status_code == 200, file["url"]
            assert response.headers["content-type"] == "font/woff2"


def test_icon_sheet_loads(client):
    sprite = get_style(client)["sprite"].removeprefix(ORIGIN)
    # MapLibre asks for these four files: the icon list and picture, at normal and double resolution.
    for suffix, media_type in [(".json", "application/json"), (".png", "image/png"),
                               ("@2x.json", "application/json"), ("@2x.png", "image/png")]:
        response = client.get(sprite + suffix)
        assert response.status_code == 200, sprite + suffix
        assert response.headers["content-type"] == media_type


def test_missing_asset_is_404(client):
    assert client.get("/maps/fonts/no-such-font.woff2").status_code == 404
    # %5C is a backslash: on Windows this name would climb out of the fonts folder.
    assert client.get("/maps/fonts/..%5C..%5Croutes.py").status_code == 404


def test_asset_names_stay_inside_their_folder():
    # Checked directly rather than through an address, so this fails on any computer if the rule
    # breaks. Through an address, a backslash name is refused on a Mac anyway, for another reason.
    assert is_asset_name("ofm@2x.png")
    assert is_asset_name("noto-sans-latin-400-normal.woff2")
    for name in ["..", ".hidden", "..\\..\\routes.py", "a/b", "C:secret", ""]:
        assert not is_asset_name(name), name


def test_terrain_max_zoom_comes_from_the_pack(make_pack, client, monkeypatch):
    # A made-up terrain pack whose last zoom is 14, like the POC's.
    monkeypatch.setenv(TERRAIN_SETTING, make_pack({(14, 0, 0): b"tile"}, TileType.WEBP, Compression.NONE))
    assert get_style(client)["sources"]["terrain"]["maxzoom"] == 14


def test_terrain_max_zoom_without_a_pack(client, monkeypatch):
    monkeypatch.delenv(TERRAIN_SETTING, raising=False)
    assert get_style(client)["sources"]["terrain"]["maxzoom"] == 12
