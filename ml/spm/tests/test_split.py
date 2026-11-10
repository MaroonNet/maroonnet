import pytest

from spm.cases.split import load_holdout, make_holdout, partition, write_holdout
from spm.schema import Case, LonLat


def cases():
    out = []
    for i in range(30):
        cat = "hiker" if i < 20 else "hunter"
        terr = "flat" if i % 3 else "mountainous"
        out.append(Case(f"t:{i:02d}", "t", LonLat(-111.0, 34.0), cat, terrain=terr))
    out.append(Case("t:solo", "t", LonLat(-111.0, 34.0), "child", terrain="flat"))  # stratum of 1
    return out


def test_holdout_is_stratified_deterministic_and_frozen(tmp_path):
    pool = cases()
    ids = make_holdout(pool, frac=1 / 3, seed=7)
    assert ids == make_holdout(pool, frac=1 / 3, seed=7)  # same seed, same draw
    assert ids != make_holdout(pool, frac=1 / 3, seed=8)
    assert "t:solo" not in ids  # a stratum of one is never held out
    by_id = {c.case_id: c for c in pool}
    hunters = [i for i in ids if by_id[i].category == "hunter"]
    assert 2 <= len(hunters) <= 4 and 8 <= len(ids) <= 12  # about a third of each stratum
    path = write_holdout(tmp_path / "holdout.yaml", ids, "t", 1 / 3, 7)
    assert load_holdout(path) == set(ids)
    with pytest.raises(FileExistsError):
        write_holdout(path, ids[:2], "t", 1 / 3, 7)
    write_holdout(path, ids[:2], "t", 1 / 3, 7, force=True)
    assert load_holdout(path) == set(ids[:2])
    train, test = partition(pool, set(ids))
    assert len(train) + len(test) == len(pool) and not {c.case_id for c in train} & set(ids)
    assert load_holdout(tmp_path / "missing.yaml") == set()
