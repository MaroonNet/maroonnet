"""Run every adapter, validate, and write one harmonized cases table.

Adding a new source (YOSAR, Oregon, ...) means writing one adapter
module with ``NAME``, ``fetch(dest)`` and ``load(src_dir) -> list[Case]`` and
registering it in ``ADAPTERS``. Nothing downstream changes.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from spm.cases.adapters import mapscore, nysdec
from spm.cases.validate import haversine_m, validate
from spm.schema import Case, LonLat

ADAPTERS = {mapscore.NAME: mapscore, nysdec.NAME: nysdec}

COLUMNS = [
    "case_id",
    "source",
    "region",
    "category",
    "category_raw",
    "ipp_type",
    "ipp_lon",
    "ipp_lat",
    "find_lon",
    "find_lat",
    "dist_km",
    "age",
    "sex",
    "party_size",
    "ecoregion",
    "terrain",
    "elapsed_h",
    "status",
    "notes",
    "extra",
]


def to_frame(cases: list[Case]) -> pd.DataFrame:
    rows = []
    for c in cases:
        d = asdict(c)
        ipp, find = d.pop("ipp"), d.pop("find")
        d["ipp_lon"], d["ipp_lat"] = ipp or (None, None)
        d["find_lon"], d["find_lat"] = find or (None, None)
        d["dist_km"] = round(haversine_m(c.ipp, c.find) / 1000, 4) if c.ipp and c.find else None
        d["extra"] = json.dumps(d["extra"])
        rows.append(d)
    return pd.DataFrame(rows, columns=COLUMNS)


def from_frame(df: pd.DataFrame) -> list[Case]:
    cases = []
    for r in df.to_dict("records"):
        r = {k: (None if isinstance(v, float) and pd.isna(v) else v) for k, v in r.items()}
        ilon, ilat, flon, flat = (r.pop(k) for k in ("ipp_lon", "ipp_lat", "find_lon", "find_lat"))
        ipp = LonLat(ilon, ilat) if ilon is not None else None
        find = LonLat(flon, flat) if flon is not None else None
        r.pop("dist_km")
        r["extra"] = json.loads(r["extra"]) if r.get("extra") else {}
        if r.get("party_size") is not None:
            r["party_size"] = int(r["party_size"])
        cases.append(Case(ipp=ipp, find=find, **r))
    return cases


def harmonize(
    data_dir: Path, sources: list[str] | None = None, download: bool = True
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Fetch (optionally), load, validate and write ``cases.csv`` + ``case_issues.csv``."""
    cases_dir = data_dir / "cases"
    all_cases: list[Case] = []
    bboxes = {}
    for name in sources or list(ADAPTERS):
        adapter = ADAPTERS[name]
        src = cases_dir / "sources" / name
        if download:
            adapter.fetch(src)
        all_cases += adapter.load(src)
        if hasattr(adapter, "BBOX"):
            bboxes[name] = adapter.BBOX
    kept, issues = validate(all_cases, bboxes)
    df = to_frame(kept)
    cases_dir.mkdir(parents=True, exist_ok=True)
    df.to_csv(cases_dir / "cases.csv", index=False)
    issues.to_csv(cases_dir / "case_issues.csv", index=False)
    return df, issues


def load_cases(data_dir: Path) -> list[Case]:
    return from_frame(pd.read_csv(data_dir / "cases" / "cases.csv"))
