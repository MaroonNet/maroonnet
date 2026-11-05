"""Leave-one-region-out evaluation of terrain models on find-only cases (e.g. NYS DEC).

Find-only cases have no IPP, so there is no ring and no MapScore window.
Each case is scored inside its own find-centred disc (HybridModel._find_stratum):

    loglik         log P(find cell) within the disc. A proper score: it rewards
                   calibration, not only ranking. Flat map: -log(cells in disc).
    disc_mapscore  MapScore's rank formula (eval.mapscore) applied to the disc
                   cells. Flat map: 0; find ranked first: ~1.

Folds hold out one region at a time. A held-out region contributed nothing to
training, so it is scored with the shared weights only (no region correction).
Strata are built once per model configuration and reused across folds.

This measures how well terrain weights transfer between regions. It is not
Gate B: there is no ring, and the disc is centred on the find.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
import pandas as pd
from scipy.special import logsumexp

from spm.models.hybrid import HybridModel, Stratum
from spm.schema import Case

UNIFORM = "uniform"


def score_stratum(st: Stratum, w: np.ndarray) -> tuple[float, float]:
    """(log-likelihood of the find cell, disc MapScore) under weights ``w``."""
    s = st.logoff + st.design.log_intensity(w)
    loglik = float(s[0] - logsumexp(s))
    n = np.count_nonzero(s > s[0])
    m = np.count_nonzero(s == s[0])
    r = (n + m / 2.0) / s.size
    return loglik, (0.5 - r) / 0.5


def leave_one_region_out(
    models: dict[str, Callable[[], HybridModel]], cases: list[Case]
) -> pd.DataFrame:
    """Per-case scores for every model plus a flat-map baseline (model ``uniform``).

    All models must use the same ``res`` and ``find_radius_m`` so they score the
    same disc cells; ``feature_res``, features and penalties may differ.
    """
    grids = {(f().res, f().find_radius_m) for f in models.values()}
    if len(grids) != 1:
        raise ValueError(f"models score different discs (res, find_radius_m): {grids}")
    rows = []
    for name, factory in models.items():
        strata = [s for s in factory().strata(cases) if s.find_only]
        for region in sorted({s.region for s in strata}):
            train = [s for s in strata if s.region != region]
            test = [s for s in strata if s.region == region]
            if not train:
                continue
            m = factory().fit_strata(train)
            for st in test:
                loglik, ms = score_stratum(st, m.w)
                rows.append(_row(name, st, loglik, ms))
                if name == next(iter(models)):  # baseline once, on the same discs
                    rows.append(_row(UNIFORM, st, -np.log(st.design.n_cells), 0.0))
    return pd.DataFrame(rows)


def _row(model: str, st: Stratum, loglik: float, ms: float) -> dict:
    return {
        "model": model,
        "case_id": st.case_id,
        "region": st.region,
        "n_cells": st.design.n_cells,
        "loglik": loglik,
        "disc_mapscore": ms,
    }


def paired_summary(
    per_case: pd.DataFrame, baseline: str = UNIFORM, n_boot: int = 5000, seed: int = 0
) -> pd.DataFrame:
    """Mean scores per model, and the paired per-case log-likelihood gain over ``baseline``
    with a case-level bootstrap 95% CI."""
    rng = np.random.default_rng(seed)
    base = per_case[per_case["model"] == baseline].set_index("case_id")["loglik"]
    out = []
    for name, g in per_case.groupby("model", sort=False):
        g = g.set_index("case_id")
        d = (g["loglik"] - base.reindex(g.index)).to_numpy()
        boots = rng.choice(d, size=(n_boot, d.size), replace=True).mean(axis=1)
        out.append(
            {
                "model": name,
                "n_cases": len(g),
                "mean_loglik": g["loglik"].mean(),
                f"gain_vs_{baseline}": d.mean(),
                "ci95_low": np.percentile(boots, 2.5),
                "ci95_high": np.percentile(boots, 97.5),
                "frac_better": float((d > 0).mean()),
                "mean_disc_mapscore": g["disc_mapscore"].mean(),
            }
        )
    return pd.DataFrame(out).round(3)


def by_region(per_case: pd.DataFrame, baseline: str = UNIFORM) -> pd.DataFrame:
    """Mean log-likelihood gain over ``baseline`` per held-out region and model."""
    base = per_case[per_case["model"] == baseline].set_index("case_id")["loglik"]
    df = per_case[per_case["model"] != baseline].copy()
    df["gain"] = df["loglik"].to_numpy() - base.reindex(df["case_id"]).to_numpy()
    table = df.pivot_table(index="region", columns="model", values="gain", aggfunc="mean")
    table.insert(0, "n_cases", df.groupby("region")["case_id"].nunique())
    return table.round(3)
