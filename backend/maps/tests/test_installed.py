"""Finding the packs installed in the maps folder."""

from maps.installed import pack_folders


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
