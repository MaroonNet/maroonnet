"""Finding the packs installed in the maps folder."""

import pytest

from maps.installed import pack_folders, read_pack_infos


def test_only_folders_in_the_agreed_layout_are_found(tmp_path):
    for folder in ["state/CO/basemap", "state/CO/terrain", "state/UT/basemap", "mission/brainard-lake",
                   "backup/old-colorado", "state/CO/extra"]:
        (tmp_path / folder).mkdir(parents=True)
    (tmp_path / "mission" / "notes.txt").write_text("a file, not a pack folder")

    found = pack_folders(tmp_path)

    assert list(found) == ["mission/brainard-lake", "state/CO/basemap", "state/CO/terrain", "state/UT/basemap"]
    assert found["state/CO/terrain"] == tmp_path / "state" / "CO" / "terrain"


def test_an_empty_maps_folder_has_no_packs(tmp_path):
    assert pack_folders(tmp_path) == {}


def test_each_pack_json_is_read_by_id(tmp_path, write_pack_json):
    write_pack_json(tmp_path / "state/CO/terrain")
    write_pack_json(tmp_path / "state/CO/basemap", contents="basemap", file="basemap-2026-10-23.pmtiles")
    write_pack_json(tmp_path / "mission/brainard-lake", kind="mission", name="Brainard Lake")
    (tmp_path / "state/UT/terrain").mkdir(parents=True)  # no pack.json: skipped

    infos = read_pack_infos(tmp_path)

    assert list(infos) == ["mission/brainard-lake", "state/CO/basemap", "state/CO/terrain"]
    assert infos["mission/brainard-lake"].name == "Brainard Lake"


@pytest.mark.parametrize("folder, changes", [
    ("state/CO/basemap", {}),                                       # says terrain
    ("state/CO/terrain", {"kind": "mission"}),                      # says mission
    ("mission/brainard-lake", {}),                                  # says state
    ("mission/brainard-lake", {"kind": "mission", "contents": "basemap"}),  # missions hold terrain only
])
def test_a_pack_json_that_disagrees_with_its_folder_is_skipped(tmp_path, capsys, write_pack_json,
                                                                folder, changes):
    write_pack_json(tmp_path / folder, **changes)
    assert read_pack_infos(tmp_path) == {}
    assert "but its folder holds" in capsys.readouterr().out
