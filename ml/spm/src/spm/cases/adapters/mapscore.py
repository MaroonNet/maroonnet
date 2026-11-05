"""Adapter for the free MapScore case set (github.com/ctwardy/mapscore, case_in/).

What the files actually contain (checked 2026-09-24):
  * input_unsorted.csv: 131 rows, all Arizona (despite the README also naming
    New York and Yosemite). Columns: Case_Name, IPP Lat, IPP Lon, Find Lat,
    Find Lot [sic], Watershed, SubjectCategory, Eco Region, Terrain, Distance.
    The Distance column does not match the coordinates in any consistent unit,
    so it is ignored; distance is recomputed from coordinates.
  * exported_case_Library.txt: 14 richer records ('|' fields, '$' separated)
    with ISRID id, scenario, age, sex, party size and narrative. Joined onto
    the CSV rows by coordinates.

Licensing: the README says the Arizona, New York and Yosemite cases "are free
for distribution". The repository has no LICENSE file, so the files are
downloaded at build time rather than committed to this repo.
"""

from __future__ import annotations

import urllib.request
from pathlib import Path

import pandas as pd

from spm.cases.categories import normalize
from spm.schema import Case, LonLat

NAME = "mapscore"
RAW_BASE = "https://raw.githubusercontent.com/ctwardy/mapscore/master/case_in/"
FILES = ("input_unsorted.csv", "exported_case_Library.txt")

CROSSWALK = {
    "mental retardation": "intellectual_disability",  # ISRID's older label
    "vehicle-4wd": "vehicle_4wd",
    "horseback rider": "horseback_rider",
    "mountain biker": "mountain_biker",
    "substance abuse": "substance_abuse",
}

LIBRARY_FIELDS = [
    "name",
    "isrid_id",
    "category",
    "subject_detail",
    "scenario",
    "activity",
    "age",
    "sex",
    "party_size",
    "party_sexes",
    "ecoregion",
    "ecoregion_code",
    "terrain",
    "ipp_lat",
    "ipp_lon",
    "find_lat",
    "find_lon",
    "time_a",
    "time_b",
    "time_c",
    "notes",
]


def fetch(dest: Path) -> list[Path]:
    """Download the case files into ``dest`` (skips files already present)."""
    dest.mkdir(parents=True, exist_ok=True)
    out = []
    for fname in FILES:
        path = dest / fname
        if not path.exists():
            urllib.request.urlretrieve(RAW_BASE + fname, path)
        out.append(path)
    return out


def _read_library(path: Path) -> pd.DataFrame:
    text = path.read_text(encoding="latin-1")
    rows = [r.split("|") for r in text.split("$") if r.strip()]
    rows = [r for r in rows if len(r) == len(LIBRARY_FIELDS)]
    lib = pd.DataFrame(rows, columns=LIBRARY_FIELDS)
    for c in ("ipp_lat", "ipp_lon", "find_lat", "find_lon"):
        lib[c] = pd.to_numeric(lib[c], errors="coerce").round(5)
    lib["notes"] = lib["notes"].str.replace("\\'", "'", regex=False).str.strip()
    return lib


def _num(v):
    """First number in a field like '58,20' (party ages); None if absent."""
    try:
        return float(str(v).split(",")[0])
    except (TypeError, ValueError):
        return None


def _field(row: pd.Series, col: str):
    """Return row[col], or None when the column is absent, NaN, or "unknown"."""
    if col not in row or pd.isna(row[col]) or row[col] == "unknown":
        return None
    return row[col]


def load(src_dir: Path) -> list[Case]:
    """Read the downloaded files and return harmonized Cases."""
    df = pd.read_csv(src_dir / "input_unsorted.csv").dropna(subset=["IPP Lat", "IPP Lon"])
    key = ["ipp_lat", "ipp_lon", "find_lat", "find_lon"]
    df[key] = df[["IPP Lat", "IPP Lon", "Find Lat", "Find Lot"]].round(5).to_numpy()

    lib_path = src_dir / "exported_case_Library.txt"
    if lib_path.exists():
        lib = _read_library(lib_path).drop_duplicates(subset=key)
        df = df.merge(lib.drop(columns=["category", "ecoregion", "terrain"]), on=key, how="left")

    cases = []
    for _, r in df.iterrows():
        find = None
        if pd.notna(r["Find Lat"]) and pd.notna(r["Find Lot"]):
            find = LonLat(float(r["Find Lot"]), float(r["Find Lat"]))
        party = _num(_field(r, "party_size"))
        cases.append(
            Case(
                case_id=f"{NAME}:{r['Case_Name']}",
                source=NAME,
                ipp=LonLat(float(r["IPP Lon"]), float(r["IPP Lat"])),
                find=find,
                ipp_type="unknown",
                category=normalize(r["SubjectCategory"], CROSSWALK),
                category_raw=None if pd.isna(r["SubjectCategory"]) else str(r["SubjectCategory"]),
                age=_num(_field(r, "age")),
                sex=_field(r, "sex"),
                party_size=int(party) if party else None,
                ecoregion=str(r["Eco Region"]).strip().lower()
                if pd.notna(r["Eco Region"])
                else None,
                terrain=str(r["Terrain"]).strip().lower() if pd.notna(r["Terrain"]) else None,
                region="US-AZ",
                notes=_field(r, "notes"),
                extra={
                    "isrid_id": _field(r, "isrid_id"),
                    "scenario": _field(r, "scenario"),
                    "watershed_raw": None if pd.isna(r["Watershed"]) else int(r["Watershed"]),
                    "times_raw": [_field(r, "time_a"), _field(r, "time_b"), _field(r, "time_c")],
                },
            )
        )
    return cases
