"""The model file: everything needed to predict, as one JSON document.

A fitted SPM model is small: a few terrain log-multipliers, a lognormal ring per
subject category, the feature ranges seen in training (for out-of-range flags)
and the grid settings. ``save_model`` writes them with provenance;
``load_model`` rebuilds the model object, given a stack provider for the
terrain it will run on. A saved and reloaded model predicts identically
(tests/test_artifact.py).

The file holds no case data and no coordinates of any person.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from spm.features.spec import FeatureSpec
from spm.models.bayes import BayesModel
from spm.models.hybrid import HybridModel
from spm.models.ring import RingModel

FORMAT = 1


def _spec_to_dict(s: FeatureSpec) -> dict:
    return {"name": s.name, "edges": list(s.edges), "prior": list(s.prior), "source": s.source}


def _spec_from_dict(d: dict) -> FeatureSpec:
    return FeatureSpec(
        name=d["name"],
        edges=tuple(float(e) for e in d["edges"]),
        prior=tuple(None if v is None else float(v) for v in d["prior"]),
        source=d.get("source", ""),
    )


def _ring_to_dict(r: RingModel) -> dict:
    return {
        "name": r.name,
        "min_cases": r.min_cases,
        "pooled_only": r.pooled_only,
        "quantiles": r.quantiles,
        "params": {k: [float(mu), float(sigma)] for k, (mu, sigma) in r.params.items()},
        "n_fit": dict(r.n_fit),
    }


def _ring_from_dict(d: dict) -> RingModel:
    r = RingModel(min_cases=d["min_cases"], quantiles=d["quantiles"], pooled_only=d["pooled_only"])
    r.name = d.get("name", r.name)
    r.params = {k: (v[0], v[1]) for k, v in d["params"].items()}
    r.n_fit = {k: int(v) for k, v in d["n_fit"].items()}
    return r


def to_dict(model: HybridModel | BayesModel, meta: dict | None = None) -> dict:
    """JSON-ready description of a fitted model."""
    doc = {
        "format": FORMAT,
        "created_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "name": model.name,
        "version": model.version,
        "specs": [_spec_to_dict(s) for s in model.specs],
        "feature_res": model.feature_res,
        "ring": _ring_to_dict(model.prior),
        "meta": meta or {},
    }
    if isinstance(model, HybridModel):
        doc.update(
            kind="hybrid",
            res=model.res,
            side_m=model.side_m,
            find_radius_m=model.find_radius_m,
            lam_w=model.lam_w,
            lam_region=model.lam_region,
            w=[float(v) for v in model.w],
            delta={k: [float(v) for v in d] for k, d in model.delta.items()},
            ranges={k: [float(lo), float(hi)] for k, (lo, hi) in model.ranges.items()},
            max_logm=model.max_logm,
            n_train=int(model.n_train),
            n_find_only=int(getattr(model, "n_find_only", 0)),
        )
    elif isinstance(model, BayesModel):
        doc["kind"] = "model_a"
        doc["max_multiplier"] = model.max_multiplier
    else:
        raise TypeError(f"cannot save a {type(model).__name__}")
    return doc


def from_dict(doc: dict, stack_provider=None) -> HybridModel | BayesModel:
    """Rebuild a model from ``to_dict`` output; ``stack_provider`` gives terrain at predict time."""
    if doc.get("format") != FORMAT:
        raise ValueError(f"model file format {doc.get('format')!r}, expected {FORMAT}")
    specs = [_spec_from_dict(s) for s in doc["specs"]]
    ring = _ring_from_dict(doc["ring"])
    if doc["kind"] == "hybrid":
        m = HybridModel(
            specs,
            stack_provider,
            prior=ring,
            side_m=doc["side_m"],
            res=doc["res"],
            lam_w=doc["lam_w"],
            lam_region=doc["lam_region"],
            find_radius_m=doc["find_radius_m"],
            feature_res=doc["feature_res"],
            fit_terrain=False,
        )
        m.w = np.array(doc["w"], dtype=float)
        m.delta = {k: np.array(v, dtype=float) for k, v in doc["delta"].items()}
        m.ranges = {k: (v[0], v[1]) for k, v in doc["ranges"].items()}
        m.n_train, m.n_find_only = doc["n_train"], doc["n_find_only"]
        m.max_logm = doc.get("max_logm")
    elif doc["kind"] == "model_a":
        m = BayesModel(
            specs,
            prior=ring,
            stack_provider=stack_provider,
            feature_res=doc["feature_res"],
            max_multiplier=doc.get("max_multiplier"),
        )
    else:
        raise ValueError(f"unknown model kind {doc['kind']!r}")
    m.name, m.version = doc["name"], doc["version"]
    return m


def save_model(model: HybridModel | BayesModel, path: Path, meta: dict | None = None) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(to_dict(model, meta), indent=2) + "\n")
    return path


def load_model(path: Path, stack_provider=None) -> HybridModel | BayesModel:
    return from_dict(json.loads(Path(path).read_text()), stack_provider)
