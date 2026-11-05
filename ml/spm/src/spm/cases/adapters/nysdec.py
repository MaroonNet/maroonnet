"""Adapter for NYS DEC Forest Ranger wildland search and rescue missions.

Source: "Wildland Search and Rescue Missions by NYS Forest Rangers: Beginning
2012", data.ny.gov dataset u6hu-h7p5 (Socrata). Licensing: published on Open
NY; its terms of use were not checked. The file holds real people's find
locations, so it is downloaded at build time and never committed.

What the file actually contains (checked 2026-11-03):
  * 6,779 rows, one per subject. A party is several rows with the same
    incident_number and the same find point, so rows are collapsed to one
    Case per incident.
  * location_found_latitude/longitude: WGS84/NAD83, 5 decimals. This is the
    only coordinate. The last known point is given only as county and
    municipality, so every Case here has ``ipp=None`` ("find-only"). Find-only
    cases can train terrain effects around the find but not the distance ring.
  * response_type: Search, Rescue, Recovery, Fugitive Search. Only Search is
    loaded: in a rescue the subject's location was already known.
  * Some find points repeat exactly across unrelated incidents (up to 15 times).
    Those are probably trailheads, parking areas or roads where subjects walked
    out. ``validate`` flags them; the adapter keeps them.
  * location_found_elevation has no stated unit, so it is kept raw in ``extra``.
  * Start and closed times are when rangers deployed and demobilized, not when
    the subject was last seen or found, so ``elapsed_h`` stays None.
"""

from __future__ import annotations

import urllib.request
from pathlib import Path

import pandas as pd

from spm.cases.categories import normalize
from spm.schema import Case, LonLat

NAME = "nysdec"
URL = "https://data.ny.gov/resource/u6hu-h7p5.csv?$limit=100000"
FILE = "u6hu-h7p5.csv"
RESPONSE_TYPES = {"Search"}
# lon_min, lat_min, lon_max, lat_max: New York State with a small margin
BBOX = (-79.9, 40.4, -71.7, 45.1)

# Only activities with an unambiguous Koester category are mapped. Walking,
# Runaway, Biking, Fishing, Boating, etc. stay "unknown" (raw label kept)
# until the team decides how to map them.
CROSSWALK = {
    "hiking": "hiker",
    "hunting": "hunter",
    "despondent": "despondent",
    "camping": "camper",
    "off road vehicle/atv": "atv",
    "snowmobile": "snowmobiler",
    "skiing": "skier",
    "climbing:rock/ice": "climber",
    "horseback riding": "horseback_rider",
    "aircraft": "aircraft",
    "motor vehicle": "vehicle",
}


def fetch(dest: Path) -> list[Path]:
    """Download the mission table into ``dest`` (skips the file if present)."""
    dest.mkdir(parents=True, exist_ok=True)
    path = dest / FILE
    if not path.exists():
        urllib.request.urlretrieve(URL, path)
    return [path]


def _str(v) -> str | None:
    if v is None or pd.isna(v) or not str(v).strip():
        return None
    return str(v).strip()


def _float(v) -> float | None:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if pd.isna(f) else f


def _bool(v) -> bool | None:
    s = _str(v)
    return None if s is None else s.lower() == "true"


def load(src_dir: Path) -> list[Case]:
    """Read the downloaded table and return one find-only Case per search incident."""
    df = pd.read_csv(src_dir / FILE, dtype=str)
    df = df[df["response_type"].isin(RESPONSE_TYPES)]
    df = df.sort_values(["incident_number", "subject_number"], kind="stable")

    cases = []
    for incident, g in df.groupby("incident_number", sort=False):
        r = g.iloc[0]
        lat, lon = _float(r["location_found_latitude"]), _float(r["location_found_longitude"])
        find = LonLat(lon, lat) if lat is not None and lon is not None else None
        activity = _str(r["activity"])
        cases.append(
            Case(
                case_id=f"{NAME}:{incident}",
                source=NAME,
                ipp=None,
                find=find,
                category=normalize(activity, CROSSWALK),
                category_raw=activity,
                age=_float(r["subject_age"]),
                sex=_str(r["subject_gender"]),
                party_size=len(g),
                region=f"US-NY-R{_str(r['incident_region'])}",
                extra={
                    "situation": _str(r["situation"]),
                    "activity": activity,
                    "ages": [_float(a) for a in g["subject_age"]],
                    "start_date": _str(r["start_date"]),
                    "elevation_raw": _str(r["location_found_elevation"]),
                    "found_in_search_area": _bool(r["found_in_search_area"]),
                    "technique": _str(r["technique"]),
                    "lkp_land_class": _str(r["last_known_point_land_class"]),
                    "lkp_county": _str(r["last_known_point_county"]),
                    "lkp_municipality": _str(r["last_known_point_municipality"]),
                    "adirondack_park": _bool(r["incident_adirondack_park"]),
                    "catskill_park": _bool(r["incident_catskill_park"]),
                    "rows_disagree_on_find": len(
                        g[["location_found_latitude", "location_found_longitude"]].drop_duplicates()
                    )
                    > 1,
                },
            )
        )
    return cases
