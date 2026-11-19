"""Region-holdout evaluation of find-only terrain models (synthetic; says nothing about people)."""

import numpy as np
import pytest
from test_hybrid_find_only import find_only, hybrid, world_and_cases  # noqa: F401

from spm.eval.find_only import (
    UNIFORM,
    by_region,
    leave_one_region_out,
    paired_summary,
    score_stratum,
)
from spm.features.aggregate import SubcellDesign
from spm.features.spec import FeatureSpec
from spm.models.hybrid import HybridModel, Stratum


def test_score_stratum_flat_and_informative():
    x = np.eye(2)[[0, 1, 1, 1]].astype(np.float32)  # find cell in bin 0, three others in bin 1
    st = Stratum("c", "R", np.zeros(4), SubcellDesign.from_cell_bins(x), {}, True)
    ll, ms = score_stratum(st, np.zeros(2))
    assert ll == pytest.approx(-np.log(4)) and ms == 0.0
    ll, ms = score_stratum(st, np.array([2.0, 0.0]))
    assert ll > -np.log(4) and ms > 0.7


def test_fit_strata_matches_fit(world_and_cases):  # noqa: F811
    world, cases = world_and_cases
    cases = find_only(cases[:15])
    a = hybrid(world).fit(cases)
    m = hybrid(world)
    b = m.fit_strata(m.strata(cases))
    np.testing.assert_allclose(a.w, b.w)
    assert a.ranges == b.ranges and a.n_find_only == b.n_find_only == 15


class PlantedStrata(HybridModel):
    """HybridModel whose strata are generated directly: in every region, a find
    in each disc is drawn with P(cell) proportional to exp(x @ W_TRUE)."""

    def strata(self, cases):
        rng = np.random.default_rng(0)
        out = []
        for region in ("R1", "R2", "R3"):
            for i in range(100):
                x = np.eye(3, dtype=np.float32)[rng.choice(3, size=300, p=[0.05, 0.15, 0.8])]
                p = np.exp(x @ W_TRUE)
                k = rng.choice(300, p=p / p.sum())
                x[[0, k]] = x[[k, 0]]  # find cell first
                design = SubcellDesign.from_cell_bins(x)
                out.append(Stratum(f"{region}-{i}", region, np.zeros(300), design, {}, True))
        return out


W_TRUE = np.log([6.0, 2.0, 1.0])
SPEC3 = FeatureSpec("dist_trail_m", edges=(100, 300), prior=(None, None, None))


def test_region_holdout_finds_transferable_effect():
    model = lambda: PlantedStrata([SPEC3], stack_provider=None)  # noqa: E731
    per_case = leave_one_region_out({"hybrid": model}, [])
    assert (per_case["model"] == UNIFORM).sum() == (per_case["model"] == "hybrid").sum() == 300
    s = paired_summary(per_case).set_index("model")
    assert s.loc[UNIFORM, f"gain_vs_{UNIFORM}"] == 0
    assert s.loc["hybrid", "ci95_low"] > 0  # planted effect transfers to unseen regions
    assert s.loc["hybrid", "mean_disc_mapscore"] > 0
    regions = by_region(per_case)
    assert list(regions.index) == ["R1", "R2", "R3"] and (regions["hybrid"] > 0).all()


def test_models_must_score_the_same_discs(world_and_cases):  # noqa: F811
    world, cases = world_and_cases
    models = {
        "a": lambda: hybrid(world),
        "b": lambda: hybrid(world, find_radius_m=500.0),
    }
    with pytest.raises(ValueError, match="different discs"):
        leave_one_region_out(models, find_only(cases[:5]))
