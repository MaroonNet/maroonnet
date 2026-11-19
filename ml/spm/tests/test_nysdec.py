from pathlib import Path

from spm.cases.adapters import nysdec
from spm.cases.harmonize import from_frame, to_frame
from spm.cases.validate import validate

FIX = Path(__file__).parent / "fixtures" / "nysdec"


def test_one_find_only_case_per_search_incident():
    cases = {c.case_id: c for c in nysdec.load(FIX)}
    assert "nysdec:T-2" not in cases  # rescue: location already known
    t1 = cases["nysdec:T-1"]
    assert t1.ipp is None
    assert t1.find.lon == -74.0 and t1.find.lat == 44.0
    assert t1.party_size == 2 and t1.extra["ages"] == [32.0, 30.0]
    assert t1.category == "hiker" and t1.region == "US-NY-R5"
    assert t1.extra["found_in_search_area"] is True
    assert cases["nysdec:T-3"].category == "unknown"  # Walking is not mapped
    assert cases["nysdec:T-3"].category_raw == "Walking"


def test_validate_keeps_find_only_and_flags_shared_points():
    kept, issues = validate(nysdec.load(FIX), {nysdec.NAME: nysdec.BBOX})
    ids = {c.case_id for c in kept}
    assert {"nysdec:T-1", "nysdec:T-3", "nysdec:T-4", "nysdec:T-5"} == ids
    reasons = dict(zip(issues["case_id"] + "|" + issues["action"], issues["reason"], strict=True))
    assert reasons["nysdec:T-6|drop"] == "find outside the nysdec source area"
    assert reasons["nysdec:T-7|drop"] == "missing find coordinates"
    assert reasons["nysdec:T-4|flag"] == "find point shared by 2 incidents"
    assert reasons["nysdec:T-5|flag"] == "find point shared by 2 incidents"


def test_find_only_frame_round_trip():
    kept, _ = validate(nysdec.load(FIX), {nysdec.NAME: nysdec.BBOX})
    back = from_frame(to_frame(kept))
    assert [c.ipp for c in back] == [None] * len(kept)
    assert [c.find for c in back] == [c.find for c in kept]
