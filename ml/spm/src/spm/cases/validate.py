"""Case checks run before anything is trained or scored.

Each rule either drops a case (with the reason recorded) or flags it. The
issues table is written next to the harmonized cases so every exclusion is
visible and reviewable.
"""

from __future__ import annotations

import math

import pandas as pd

from spm.schema import Case

EARTH_R_M = 6_371_008.8
MIN_DIST_M = 1.0  # find within 1 m of IPP: almost always a copied placeholder
MAX_DIST_M = 100_000.0  # beyond 100 km: likely a coordinate error, not a walk
SHARED_FIND_MIN = 2  # find-only incidents at one exact point before it is flagged


def haversine_m(a, b) -> float:
    la1, lo1, la2, lo2 = map(math.radians, (a.lat, a.lon, b.lat, b.lon))
    h = (
        math.sin((la2 - la1) / 2) ** 2
        + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    )
    return 2 * EARTH_R_M * math.asin(math.sqrt(h))


def _in_range(p) -> bool:
    return -90 <= p.lat <= 90 and -180 <= p.lon <= 180


def _in_bbox(p, bbox: tuple[float, float, float, float]) -> bool:
    lon_min, lat_min, lon_max, lat_max = bbox
    return lon_min <= p.lon <= lon_max and lat_min <= p.lat <= lat_max


def validate(
    cases: list[Case], bboxes: dict[str, tuple[float, float, float, float]] | None = None
) -> tuple[list[Case], pd.DataFrame]:
    """Return (cases kept, issues table with one row per dropped or flagged case).

    Cases with a find but no IPP ("find-only", e.g. NYS DEC) are kept; they can
    train terrain effects around the find but not the distance ring.
    ``bboxes`` maps a source name to (lon_min, lat_min, lon_max, lat_max); finds
    outside their source's box are dropped.
    """
    kept, issues, seen = [], [], {}
    bboxes = bboxes or {}

    def note(case_id: str, action: str, reason: str) -> None:
        issues.append({"case_id": case_id, "action": action, "reason": reason})

    for c in cases:
        if c.find is None:
            note(c.case_id, "drop", "missing find coordinates")
            continue
        if not (_in_range(c.find) and (c.ipp is None or _in_range(c.ipp))):
            note(c.case_id, "drop", "coordinates out of range")
            continue
        if c.source in bboxes and not _in_bbox(c.find, bboxes[c.source]):
            note(c.case_id, "drop", f"find outside the {c.source} source area")
            continue
        if c.ipp is None:
            key = (c.case_id,)
        else:
            key = (
                round(c.ipp.lon, 5),
                round(c.ipp.lat, 5),
                round(c.find.lon, 5),
                round(c.find.lat, 5),
            )
        if key in seen:
            note(c.case_id, "drop", f"duplicate of {seen[key]} (same IPP and find)")
            continue
        seen[key] = c.case_id
        if c.ipp is not None:
            d = haversine_m(c.ipp, c.find)
            if d < MIN_DIST_M:
                note(c.case_id, "drop", "find equals IPP (likely placeholder)")
                continue
            if d > MAX_DIST_M:
                note(
                    c.case_id,
                    "drop",
                    f"IPP-find distance {d / 1000:.1f} km exceeds {MAX_DIST_M / 1000:.0f} km",
                )
                continue
        if c.category == "unknown":
            note(c.case_id, "flag", f"category unmapped (raw: {c.category_raw!r})")
        kept.append(c)

    # An exact find point shared by unrelated find-only incidents is probably a
    # trailhead, parking area or road where the subject walked out, not where
    # they were lost. Flag it so terrain fits can exclude it.
    shared: dict[tuple[float, float], list[str]] = {}
    for c in kept:
        if c.ipp is None:
            shared.setdefault((round(c.find.lon, 5), round(c.find.lat, 5)), []).append(c.case_id)
    for ids in shared.values():
        if len(ids) >= SHARED_FIND_MIN:
            for case_id in ids:
                note(case_id, "flag", f"find point shared by {len(ids)} incidents")
    return kept, pd.DataFrame(issues, columns=["case_id", "action", "reason"])
