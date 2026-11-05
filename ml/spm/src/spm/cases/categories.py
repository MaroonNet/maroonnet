"""Canonical subject categories.

Names follow the ISRID / Lost Person Behavior (Koester 2008) categories in
lower_snake_case. Each adapter maps its source vocabulary onto these names
and keeps the original in ``Case.category_raw``.

This list is a starting point. The final identifier set is an open team
question (SPM v1.1 §2, §7 "Subject category identifiers").
"""

CANONICAL = {
    "aircraft",
    "atv",
    "autistic",
    "camper",
    "child",
    "climber",
    "dementia",
    "despondent",
    "gatherer",
    "hiker",
    "horseback_rider",
    "hunter",
    "intellectual_disability",
    "mental_illness",
    "motorcycle",
    "mountain_biker",
    "runner",
    "skier",
    "snowboarder",
    "snowmobiler",
    "substance_abuse",
    "vehicle",
    "vehicle_4wd",
    "worker",
    "youth",
    "dog",
    "unknown",
}


def normalize(raw: str | None, crosswalk: dict[str, str]) -> str:
    """Map a source label to a canonical category; unknown labels become 'unknown'."""
    if raw is None or (isinstance(raw, float)) or not str(raw).strip():
        return "unknown"
    key = str(raw).strip().lower()
    cat = crosswalk.get(key, key.replace(" ", "_").replace("-", "_"))
    return cat if cat in CANONICAL else "unknown"
