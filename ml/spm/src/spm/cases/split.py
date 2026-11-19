"""A frozen test set ("final exam", roadmap decision D4).

``make_holdout`` draws a stratified sample of case ids once, with a recorded
seed; ``write_holdout`` saves them to ``configs/holdout.yaml`` (ids only, no
coordinates) and refuses to overwrite the file unless told to. Everything that
trains (``spm fit``, Gate B) excludes those ids; Gate B scores on them alone.
Changing the file after results have been looked at invalidates the exam, so
the file records when and how it was made.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import yaml

from spm.schema import Case

DEFAULT_PATH = Path("configs") / "holdout.yaml"


def make_holdout(
    cases: list[Case],
    frac: float = 1 / 3,
    seed: int = 0,
    strata: tuple[str, ...] = ("category", "terrain"),
) -> list[str]:
    """Case ids for the test set: ``frac`` of every (category, terrain) stratum, at least
    one per stratum with two or more cases, drawn with ``seed``."""
    groups: dict[tuple, list[str]] = defaultdict(list)
    for c in sorted(cases, key=lambda c: c.case_id):
        groups[tuple(getattr(c, s) for s in strata)].append(c.case_id)
    rng = np.random.default_rng(seed)
    out: list[str] = []
    for key in sorted(groups, key=str):
        ids = groups[key]
        k = int(round(len(ids) * frac))
        if len(ids) >= 2:
            k = max(k, 1)
        k = min(k, len(ids) - 1) if len(ids) >= 2 else 0
        out += [ids[i] for i in sorted(rng.choice(len(ids), size=k, replace=False))]
    return sorted(out)


def write_holdout(
    path: Path, ids: list[str], source: str, frac: float, seed: int, force: bool = False
) -> Path:
    path = Path(path)
    if path.exists() and not force:
        raise FileExistsError(f"{path} exists; the test set is frozen (use --force to redraw)")
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = {
        "note": "Frozen test set: never train on these ids; do not redraw after seeing results.",
        "source": source,
        "fraction": frac,
        "seed": seed,
        "strata": ["category", "terrain"],
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "n": len(ids),
        "case_ids": ids,
    }
    path.write_text(yaml.safe_dump(doc, sort_keys=False))
    return path


def load_holdout(path: Path = DEFAULT_PATH) -> set[str]:
    """The frozen test ids, or an empty set if no holdout file exists."""
    path = Path(path)
    if not path.exists():
        return set()
    return set((yaml.safe_load(path.read_text()) or {}).get("case_ids") or [])


def partition(cases: list[Case], holdout: set[str]) -> tuple[list[Case], list[Case]]:
    """(trainable cases, test cases)."""
    train = [c for c in cases if c.case_id not in holdout]
    return train, [c for c in cases if c.case_id in holdout]
