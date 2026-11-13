"""pack.json's shape is checked, it is written and read back safely, and a damaged one is
skipped."""

import json
from datetime import date

import pytest
from pydantic import ValidationError

from maps.pack_info import PackInfo, read_pack_info, write_pack_info
from maps.tests.samples import COLORADO_TERRAIN


def test_the_colorado_terrain_label_passes():
    info = PackInfo.model_validate(COLORADO_TERRAIN)
    assert info.downloaded == date(2026, 10, 24)
    assert info.area == [(-109.06, 36.99, -102.04, 41.00)]


@pytest.mark.parametrize("field, wrong", [
    ("kind", "country"),
    ("contents", "roads"),
    ("status", "done"),
    ("max_zoom", 31),
    ("area", []),                        # no box at all
    ("area", [[-109.06, 36.99, 41.00]]),  # a box needs four numbers
    ("file", "../other/terrain.pmtiles"),  # a path out of the folder
    ("downloaded", "yesterday"),
])
def test_a_wrong_value_is_refused_by_name(field, wrong):
    with pytest.raises(ValidationError, match=field):
        PackInfo.model_validate({**COLORADO_TERRAIN, field: wrong})


def test_a_written_pack_json_reads_back_the_same(tmp_path):
    info = PackInfo.model_validate(COLORADO_TERRAIN)
    write_pack_info(tmp_path, info)
    assert read_pack_info(tmp_path) == info
    assert [file.name for file in tmp_path.iterdir()] == ["pack.json"]  # no temporary file left


def test_a_missing_pack_json_is_skipped(tmp_path, capsys):
    assert read_pack_info(tmp_path) is None
    assert "it has no pack.json" in capsys.readouterr().out


@pytest.mark.parametrize("contents", [
    b'{"format": 1, "kind": "state", ',                       # cut off part way
    json.dumps({**COLORADO_TERRAIN, "kind": "country"}).encode(),  # a wrong value
    b"\xff\xfe\x00",                                         # not text at all
])
def test_a_damaged_pack_json_is_skipped(tmp_path, capsys, contents):
    (tmp_path / "pack.json").write_bytes(contents)
    assert read_pack_info(tmp_path) is None
    assert "its pack.json is damaged" in capsys.readouterr().out


def test_an_unreadable_pack_json_is_skipped(tmp_path, capsys):
    (tmp_path / "pack.json").mkdir()  # a folder by that name cannot be read as a file
    assert read_pack_info(tmp_path) is None
    assert "its pack.json could not be read" in capsys.readouterr().out
