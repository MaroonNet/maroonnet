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


def test_layer_groups_match_the_checkbox_list(client):
    """Every layer's group has a checkbox, and every checkbox hides at least one layer.
    A misspelled group breaks one or the other."""
    style = get_style(client)
    listed = {group["id"] for group in style["metadata"]["groups"]}
    used = {layer["metadata"]["group"] for layer in style["layers"]} - {"base"}  # base is never hidden
    assert used == listed


COPERNICUS_CREDIT = ("DLR e.V. 2010-2014, Airbus Defence and Space GmbH 2014-2018, "
                     "provided under COPERNICUS by the European Union and ESA. All rights reserved.")


def test_style_carries_the_required_credits(client):
    """The OpenStreetMap and Copernicus licences require these credits (spec section 11). Terrain
    shows through the hillshade or the contours, so every terrain source carries its credit."""
    sources = get_style(client)["sources"]
    assert "© OpenStreetMap contributors" in sources["basemap"]["attribution"]
    for name in ("terrain", "contours", "contour_labels"):
        assert COPERNICUS_CREDIT in sources[name].get("attribution", ""), name


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


def test_style_survives_a_bad_terrain_pack(tmp_path, client, monkeypatch):
    junk = tmp_path / "junk.pmtiles"
    junk.write_bytes(b"not a pack")
    monkeypatch.setenv(TERRAIN_SETTING, str(junk))
    assert get_style(client)["sources"]["terrain"]["maxzoom"] == 12


def test_every_layer_draws_from_a_source_in_the_style(client):
    style = get_style(client)
    sources = style["sources"]
    for layer in style["layers"]:
        if "source" not in layer:
            continue  # the background colour
        assert layer["source"] in sources, layer["id"]
        # Contour tiles are made in the browser and hold one layer, named in their address.
        made = re.search(r"contourLayer=(\w+)", sources[layer["source"]]["tiles"][0])
        if made:
            assert layer["source-layer"] == made.group(1), layer["id"]
