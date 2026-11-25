"""The people tests use the mission tests' made-up mission files, with a few helpers of their own."""

from mission.tests.conftest import (  # noqa: F401  (pytest finds these helpers by name)
    arizona07, arizona07_file, client, clock, empty_file, make_mission, open_bear_creek,
)


def person(first: str, last: str, middle: str | None = None, phone: str | None = None) -> dict:
    """A request body for a roster person."""
    return {"first_name": first, "middle_initial": middle, "last_name": last, "phone": phone}
