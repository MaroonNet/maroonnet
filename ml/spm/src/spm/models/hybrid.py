"""Learned hybrid: ring prior x learned terrain multipliers, with regional partial pooling.

Score of a cell for a case in region r:

    s(cell) = log ring(cell) + log mean over sub-cells of exp(sum_f theta_r[f, bin_f(sub)])
    theta_r = w + delta_r

    exp(theta[f, b]) is a point multiplier for bin b of feature f. With
    ``feature_res`` (e.g. 10 m inside 100 m cells) features are binned on the
    fine grid and the intensity is averaged over each cell's sub-cells
    (features.aggregate.SubcellDesign); without it, each cell is one sub-cell.

    w        shared log-multipliers, one per feature bin, pulled toward the
             published (prior-art) values by an L2 penalty lam_w
    delta_r  a per-region correction, pulled toward 0 by lam_region. A region
             with no cases (e.g. Colorado today) has delta = 0, so it gets the
             shared model; each case from that region nudges delta a little.

Fitting is a conditional logit over {find cell} + sampled "available" cells:
maximize the probability that the find cell wins against cells drawn
uniformly from the same window. This is the same estimator ecologists use for
resource selection functions (used vs. available points), and it stays
consistent when alternatives are sampled uniformly.

Find-only cases (a find but no IPP, e.g. NYS DEC) can train the terrain
weights too. Each becomes a stratum of every cell within ``find_radius_m`` of
the find, with no ring offset: the find competes only with nearby terrain.
This is the design of Jacobs (2015), who compared finds with random points in
a 2 km circle around each find. It assumes the ring is roughly flat across the
circle; a smaller radius makes that closer to true but leaves fewer
alternatives. IPP-relative features (relative.IPP_RELATIVE) are treated as
missing in these strata, so they learn only from cases with an IPP.

Out-of-range protection: feature ranges seen in training are recorded. At
prediction time, cells whose features fall outside them are flagged, and the
learned multipliers there fall back to the published ones. The COMBINED
multiplier is also capped near the largest value training sub-cells had
(``max_logm``, the 99.5th percentile): features are multiplied as if
independent, and a region where trails, roads and washes coincide far more
than in training (Arizona vs New York) would otherwise get stacks of 30-60x
that no data supports. Capped cells are flagged too.

Status: math and code tested on synthetic stacks only (tests/test_hybrid.py).
It says nothing about real behaviour until trained on real cases with real
terrain stacks (roadmap phase 4).
"""

from __future__ import annotations

import copy
import logging
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
from scipy.optimize import minimize
from scipy.special import logsumexp

from spm.features import aggregate, relative
from spm.features.spec import FeatureSpec
from spm.geodata.grid import Window
from spm.models.bayes import apply_log_multipliers
from spm.models.ring import RingModel
from spm.schema import Case

log = logging.getLogger(__name__)

StackProvider = Callable[[Case, Window], object]
CAP_PERCENTILE = 99.5


@dataclass(frozen=True)
class Stratum:
    """One case's conditional-logit choice set: row 0 of ``design`` is the find cell."""

    case_id: str
    region: str
    logoff: np.ndarray  # log ring per cell, or zeros for find-only
    design: aggregate.SubcellDesign
    ranges: dict[str, tuple[float, float]]  # feature value ranges seen in this window
    find_only: bool
    # Bins of the find's own sub-cell. When set, the likelihood is that of the find
    # point (its sub-cell), not of its whole model cell: the exact location pins
    # down the near bins that a 100 m cell alone cannot.
    find_pattern: np.ndarray | None = None


class HybridModel:
    name = "hybrid"
    version = "1"

    def __init__(
        self,
        specs: list[FeatureSpec],
        stack_provider: StackProvider,
        prior: RingModel | None = None,
        side_m: float = 25_000,
        res: float = 100.0,
        n_alt: int = 2000,
        lam_w: float = 1.0,
        lam_region: float = 10.0,
        find_radius_m: float | None = 1000.0,
        feature_res: float | None = None,
        fit_terrain: bool = True,
        seed: int = 0,
    ):
        self.specs = specs
        self.stack_provider = stack_provider
        self.prior = prior or RingModel()
        self.side_m, self.res = side_m, res
        self.n_alt, self.lam_w, self.lam_region = n_alt, lam_w, lam_region
        self.find_radius_m = find_radius_m  # None: ignore find-only cases
        self.feature_res = feature_res  # None: features at model res
        self.fit_terrain = fit_terrain  # False: fit() refits only the ring
        self.rng = np.random.default_rng(seed)
        self.offsets = np.cumsum([0] + [s.n_bins for s in specs])
        self.K = int(self.offsets[-1])  # one parameter per feature bin
        self.w0 = np.concatenate([s.log_prior() for s in specs]) if specs else np.zeros(0)
        self.w = self.w0.copy()
        self.delta: dict[str, np.ndarray] = {}
        self.ranges: dict[str, tuple[float, float]] = {}
        self.max_logm: float | None = None  # cap on the combined log-multiplier (see module doc)
        self.n_train = 0

    # ---------- windows ----------
    def model_window(self, case: Case) -> Window | None:
        """The model-resolution window a case is fitted on: the IPP window, or the
        find-centred window for find-only cases (None if the case is not used)."""
        if case.ipp is not None:
            return Window.around(case.ipp.lon, case.ipp.lat, side_m=self.side_m, res=self.res)
        if case.find is not None and self.find_radius_m:
            side = 4 * self.find_radius_m  # margin so distance features see lines beyond the disc
            return Window.around(case.find.lon, case.find.lat, side_m=side, res=self.res)
        return None

    def stack_window(self, case: Case) -> Window | None:
        """The window this model asks its stack provider for (fine when ``feature_res``)."""
        win = self.model_window(case)
        return None if win is None else aggregate.fine_window(win, self.feature_res)[0]

    # ---------- design ----------
    def _features(self, case: Case, window: Window, ipp: bool):
        """(features on the fine grid, sub-cells per side, fine stack); None if no stack."""
        fine, factor = aggregate.fine_window(window, self.feature_res)
        stack = self.stack_provider(case, fine)
        if stack is None:
            return None
        ipp_rc = fine.rowcol(case.ipp.lon, case.ipp.lat) if ipp else None
        return relative.compute(stack, ipp_rc), factor, stack

    # ---------- training ----------
    def _ring_stratum(self, c: Case):
        """(log offset, cells, features, factor) for a case with an IPP: find + sampled cells."""
        win = self.model_window(c)
        find_rc = win.rowcol(c.find.lon, c.find.lat)
        got = self._features(c, win, ipp=True)
        if find_rc is None or got is None:
            return None
        ring = self.prior.predict(c, win).prob
        n = win.n * win.n
        find_i = find_rc[0] * win.n + find_rc[1]
        alt = self.rng.choice(n - 1, size=min(self.n_alt, n - 1), replace=False)
        alt = alt + (alt >= find_i)  # skip the find cell
        cells = np.concatenate([[find_i], alt])
        return np.log(np.maximum(ring.ravel()[cells], 1e-300)), cells, *got[:2]

    def _find_stratum(self, c: Case):
        """(zero offset, cells, features, factor) for a find-only case: all cells in the radius."""
        win = self.model_window(c)
        find_rc = win.rowcol(c.find.lon, c.find.lat)
        got = self._features(c, win, ipp=False)
        if find_rc is None or got is None:
            return None
        find_i = find_rc[0] * win.n + find_rc[1]
        d = win.distance_from(c.find.lon, c.find.lat).ravel()
        disc = np.flatnonzero(d <= self.find_radius_m)
        cells = np.concatenate([[find_i], disc[disc != find_i]])
        return np.zeros(len(cells)), cells, *got[:2]

    def strata(self, cases: list[Case]) -> list[Stratum]:
        """One conditional-logit stratum per usable case.

        Strata from cases with an IPP embed the ring as fitted when they are
        built; find-only strata do not depend on the fit, so they can be built
        once and reused across folds (see eval.find_only).
        """
        out = []
        skipped = 0
        for c in cases:
            if c.find is None:
                continue
            if c.ipp is not None:
                built = self._ring_stratum(c)
            elif self.find_radius_m:
                built = self._find_stratum(c)
            else:
                continue
            if built is None:
                skipped += 1
                continue
            logoff, cells, feats, factor = built
            fine = aggregate.fine_window(self.model_window(c), self.feature_res)[0]
            find_pattern = aggregate.point_pattern(
                self.specs, feats, fine.rowcol(c.find.lon, c.find.lat)
            )
            ranges = {}
            for s in self.specs:
                r = aggregate.value_range(feats[s.name]) if s.name in feats else None
                if r is not None:
                    ranges[s.name] = r
            out.append(
                Stratum(
                    case_id=c.case_id,
                    region=c.region or "unknown",
                    logoff=logoff,
                    design=aggregate.SubcellDesign.from_features(self.specs, feats, factor).take(
                        cells
                    ),
                    ranges=ranges,
                    find_only=c.ipp is None,
                    find_pattern=find_pattern,
                )
            )
        if skipped:
            log.warning(
                "%d of %d cases left out of training: find outside the window or no terrain",
                skipped,
                len(cases),
            )
        return out

    def fit(self, cases: list[Case]):
        self.prior.fit(cases)
        if not self.fit_terrain:
            return self
        return self.fit_strata(self.strata(cases))

    def frozen(self, name: str | None = None) -> HybridModel:
        """Copy that keeps these terrain weights and refits only a fresh ring on ``fit``.

        For scoring a region the terrain weights never saw: fit the weights once
        elsewhere, then let the evaluation folds fit the ring as usual.
        """
        m = copy.copy(self)
        m.prior = RingModel(
            min_cases=self.prior.min_cases,
            quantiles=self.prior.quantiles,
            pooled_only=self.prior.pooled_only,
        )
        m.fit_terrain = False
        if name:
            m.name = name
        return m

    def fit_strata(self, strata: list[Stratum]):
        """Fit the terrain weights on prebuilt strata (the ring is not refitted)."""
        self.n_train = len(strata)
        self.n_find_only = sum(s.find_only for s in strata)
        lo, hi = {}, {}
        for st in strata:
            for name, (a, b) in st.ranges.items():
                lo[name] = min(lo.get(name, np.inf), a)
                hi[name] = max(hi.get(name, -np.inf), b)
        self.ranges = {k: (lo[k], hi[k]) for k in lo}
        data = [(st.logoff, st.design, st.region, st.find_pattern) for st in strata]
        regions = [st.region for st in strata]
        if not data or self.K == 0:
            return self

        reg_names = sorted(set(regions))
        n_reg, n_feat = len(reg_names), self.K
        ridx = {r: i for i, r in enumerate(reg_names)}

        def unpack(x):
            return x[:n_feat], x[n_feat:].reshape(n_reg, n_feat)

        def objective(params):
            w, d = unpack(params)
            gw, gd = np.zeros(n_feat), np.zeros((n_reg, n_feat))
            nll = 0.0
            for logoff, design, reg, fp in data:
                r = ridx[reg]
                theta = w + d[r]
                s = logoff + design.log_intensity(theta)
                lse = logsumexp(s)
                weights = np.exp(s - lse)
                if fp is None:  # likelihood of the find cell
                    nll -= s[0] - lse
                    weights[0] -= 1.0  # expected minus observed
                    g = design.grad(theta, weights)
                else:  # likelihood of the find's own sub-cell
                    nll -= logoff[0] + fp @ theta - np.log(design.n_sub) - lse
                    g = design.grad(theta, weights) - fp
                gw += g
                gd[r] += g
            nll += self.lam_w * np.sum((w - self.w0) ** 2) + self.lam_region * np.sum(d**2)
            gw += 2 * self.lam_w * (w - self.w0)
            gd += 2 * self.lam_region * d
            return nll, np.concatenate([gw, gd.ravel()])

        x0 = np.concatenate([self.w0, np.zeros(n_reg * n_feat)])
        res = minimize(objective, x0, jac=True, method="L-BFGS-B")
        self.w, d = unpack(res.x)
        self.delta = {r: d[i] for r, i in ridx.items()}
        self.fit_result = res
        self.max_logm = self._training_max_logm(strata)
        return self

    def _training_max_logm(self, strata: list[Stratum], q: float = CAP_PERCENTILE) -> float:
        return training_max_logm(strata, self.w, self.delta, q)

    # ---------- inference ----------
    def multipliers(self, region: str | None = None) -> dict[str, np.ndarray]:
        """Learned multiplier per bin, per feature (exp of theta) for a region."""
        theta = self.w + self.delta.get(region, 0.0)
        return {
            s.name: np.exp(theta[self.offsets[f] : self.offsets[f + 1]])
            for f, s in enumerate(self.specs)
        }

    def predict(self, case, window, stack=None):
        ring = self.prior.predict(case, window)
        if stack is None or not self.specs:
            return apply_log_multipliers(ring, np.zeros(window.shape), self.name, self.version)
        if self.feature_res is None:
            got = relative.compute(stack, window.rowcol(case.ipp.lon, case.ipp.lat)), 1, stack
        else:  # the caller's stack is at model res; fetch the fine one
            got = self._features(case, window, ipp=True)
            if got is None:
                return apply_log_multipliers(ring, np.zeros(window.shape), self.name, self.version)
        feats, factor, fine_stack = got
        design = aggregate.SubcellDesign.from_features(self.specs, feats, factor)
        theta = self.w + self.delta.get(case.region, 0.0)
        flags = aggregate.out_of_range(self.specs, feats, self.ranges, factor)
        flags |= aggregate.no_data(fine_stack, factor)
        cap = self.max_logm
        logm = np.where(
            flags.ravel(),
            design.log_intensity(self.w0, cap=cap),
            design.log_intensity(theta, cap=cap),
        ).reshape(window.shape)
        if cap is not None:  # flag cells where any sub-cell stack was clipped
            flags |= design.any_pattern(design.patterns @ theta > cap).reshape(window.shape)
        pred = apply_log_multipliers(ring, logm, self.name, self.version)
        pred.flags = flags
        return pred


def training_max_logm(
    strata: list[Stratum], w: np.ndarray, delta: dict | None = None, q: float = CAP_PERCENTILE
) -> float:
    """``q``-th percentile of the combined log-multiplier over all sub-cells of ``strata``.

    On the NYS DEC finds, capping at this level (about 20x) is neutral to slightly
    positive for both the learned and the published weights, while 10x and below cost
    likelihood; it exists to stop feature stacks no training terrain showed (2026-11-04).
    """
    values, weights = [], []
    for st in strata:
        values.append(st.design.patterns @ (w + (delta or {}).get(st.region, 0.0)))
        weights.append(np.asarray(st.design.counts.sum(axis=0)).ravel())
    z = np.concatenate(values)
    n = np.concatenate(weights)
    order = np.argsort(z)
    cum = np.cumsum(n[order]) / n.sum()
    return float(z[order][min(np.searchsorted(cum, q / 100.0), z.size - 1)])
