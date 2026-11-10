from pathlib import Path

from spm.cases.adapters import mapscore
from spm.cases.harmonize import from_frame, to_frame
from spm.cases.validate import validate

FIX = Path(__file__).parent / "fixtures" / "mapscore"


def test_adapter_maps_categories_and_keeps_raw():
    cases = {c.case_id: c for c in mapscore.load(FIX)}
    t06 = cases["mapscore:T06"]
    assert t06.category == "intellectual_disability"
    assert t06.category_raw == "Mental Retardation"
    assert t06.ipp.lon == -105.72 and t06.find.lat == 39.73


def test_validate_drops_duplicates_and_placeholders():
    kept, issues = validate(mapscore.load(FIX))
    ids = {c.case_id for c in kept}
    assert "mapscore:T04" not in ids  # duplicate of T01
    assert "mapscore:T05" not in ids  # find == IPP
    assert "mapscore:T07" in ids  # far but plausible
    assert set(issues["action"]) == {"drop"}


def test_frame_round_trip():
    kept, _ = validate(mapscore.load(FIX))
    back = from_frame(to_frame(kept))
    assert [c.case_id for c in back] == [c.case_id for c in kept]
    assert back[0].ipp == kept[0].ipp and back[0].category == kept[0].category
