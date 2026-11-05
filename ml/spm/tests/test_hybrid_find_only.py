"""Find-centered fitting on synthetic terrain.

Finds are drawn the realistic way (ring around an IPP x a planted trail
effect), then the IPP is thrown away, as in the NYS DEC data. Every window is
cut from one large synthetic world per case, so a window around the find shows
the same terrain the find was drawn from. Says nothing about real people.
"""

import dataclasses

import numpy as np
import pytest

from spm.features import relative
from spm.features.spec import FeatureSpec
from spm.geodata.grid import Window
from spm.geodata.stack import FeatureStack
from spm.geodata.synthetic import make_stack
from spm.models.hybrid import HybridModel
from spm.models.ring import RingModel
from spm.schema import Case, LonLat

SIDE, WORLD, RES = 12_000, 20_000, 100
Q = {"hiker": {"q25": 1.0, "q50": 2.0, "q75": 4.0}}
TRAIL = FeatureSpec("dist_trail_m", edges=(100, 300), prior=(None, None, None))
ELEV = FeatureSpec("elev_change_m", edges=(0.0,), prior=(None, None))
TRUE_TRAIL_LOGM = np.log([6.0, 2.0, 1.0])  # planted: finds drawn to trails
REGIONS = {"R1": (-111.0, 34.0), "R2": (-119.5, 37.8), "R3": (-74.0, 44.0)}


class World:
    """One big synthetic stack per case; any window on the same grid is a crop of it."""

    def __init__(self):
        self.worlds: dict[str, FeatureStack] = {}

    def add(self, case_id: str, centre: LonLat, seed: int) -> None:
        w = Window.around(centre.lon, centre.lat, side_m=WORLD, res=RES)
        self.worlds[case_id] = make_stack(w, seed=seed)

    def __call__(self, case: Case, window: Window) -> FeatureStack | None:
        big = self.worlds[case.case_id]
        bw = big.window
        if window.epsg != bw.epsg or window.res != bw.res:
            return None
        r0 = int(round((bw.y0 - window.y0) / RES))
        c0 = int(round((window.x0 - bw.x0) / RES))
        if r0 < 0 or c0 < 0 or r0 + window.n > bw.n or c0 + window.n > bw.n:
            return None
        layers = {k: v[r0 : r0 + window.n, c0 : c0 + window.n] for k, v in big.layers.items()}
        return FeatureStack(window=window, layers=layers, source=big.source)


@pytest.fixture(scope="module")
def world_and_cases():
    rng = np.random.default_rng(1)
    ring = RingModel(quantiles=Q).fit([])
    world, cases = World(), []
    for reg, (lon0, lat0) in REGIONS.items():
        for i in range(40):
            cid = f"syn:{reg}-{i}"
            ipp = LonLat(lon0 + rng.uniform(-0.3, 0.3), lat0 + rng.uniform(-0.3, 0.3))
            world.add(cid, ipp, seed=len(cases))
            c = Case(case_id=cid, source="syn", ipp=ipp, category="hiker", region=reg)
            w = Window.around(ipp.lon, ipp.lat, side_m=SIDE, res=RES)
            feats = relative.compute(world(c, w), w.rowcol(ipp.lon, ipp.lat))
            p = ring.predict(c, w).prob * np.exp(
                TRUE_TRAIL_LOGM[TRAIL.bin_index(feats["dist_trail_m"])]
            )
            k = rng.choice(p.size, p=(p / p.sum()).ravel())
            xs, ys = w.cell_centers()
            find = LonLat(*w.unproject(xs[k % w.n], ys[k // w.n]))
            cases.append(dataclasses.replace(c, find=find))
    return world, cases


def find_only(cases):
    return [dataclasses.replace(c, ipp=None) for c in cases]  # IPP thrown away


def hybrid(world, **kw):
    return HybridModel(
        [TRAIL, ELEV], world, prior=RingModel(quantiles=Q), side_m=SIDE, res=RES, **kw
    )


def trail_shape(m):
    learned = np.log(m.multipliers()["dist_trail_m"])
    return learned - learned[-1]  # relative to the far bin


def test_find_only_fit_matches_ipp_fit_on_same_finds(world_and_cases):
    # With 120 cases a single fit scatters about +-0.45 around the truth (checked
    # over seeds), so compare against the full IPP fit on the same finds instead.
    world, cases = world_and_cases
    full = hybrid(world, lam_w=0.1, lam_region=50).fit(cases)
    fo = hybrid(world, lam_w=0.1, lam_region=50).fit(find_only(cases))
    assert fo.n_find_only == len(cases)
    a, b = trail_shape(full), trail_shape(fo)
    assert b[0] > b[1] > 0 and b[0] > 0.8  # near-trail finds clearly favoured
    np.testing.assert_allclose(b, a, atol=0.5)


def test_ipp_relative_features_get_no_signal_from_find_only(world_and_cases):
    world, cases = world_and_cases
    m = hybrid(world).fit(find_only(cases[:20]))
    elev = slice(m.offsets[1], m.offsets[2])
    np.testing.assert_allclose(m.w[elev], m.w0[elev], atol=1e-6)  # stays at its prior
    assert "elev_change_m" not in m.ranges


def test_find_radius_none_ignores_find_only(world_and_cases):
    world, cases = world_and_cases
    m = hybrid(world, find_radius_m=None).fit(find_only(cases[:10]))
    assert m.n_train == 0 and m.n_find_only == 0
