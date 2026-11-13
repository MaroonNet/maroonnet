"""pack.json's shape is checked: a label with a wrong value is refused."""

from datetime import date

import pytest
from pydantic import ValidationError

from maps.pack_info import PackInfo

COLORADO_TERRAIN = {
    "format": 1,
    "kind": "state",
    "contents": "terrain",
    "name": "Colorado",
    "file": "terrain-z0-12.pmtiles",
    "area": [[-109.06, 36.99, -102.04, 41.00]],
    "min_zoom": 0,
    "max_zoom": 12,
    "source_urls": ["https://download.mapterhorn.com/planet.pmtiles"],
    "data_date": None,
    "downloaded": "2026-10-24",
    "bytes": 683000000,
    "status": "complete",
}


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
