"""Checking a time zone name.

A mission saves the name of its time zone, such as America/Denver. A zone's name carries its
own daylight saving rule, so there is one name for each zone and no separate summer name.
"""

from typing import Annotated
from zoneinfo import ZoneInfo

from pydantic import AfterValidator


def checked_time_zone(name: str) -> str:
    try:
        ZoneInfo(name)
    except (KeyError, ValueError, OSError):  # each is raised for some kind of name that is not a zone
        raise ValueError(f"{name} is not a time zone")
    return name


# A time zone name in a request. A name that is not a real zone is refused.
TimeZoneName = Annotated[str, AfterValidator(checked_time_zone)]
