"""pack.json: the small file in each pack's folder that says what the pack is (spec 8.3)."""

from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, Field

# One box: [west, south, east, north] in degrees, as the manifest writes state boxes.
Box = tuple[float, float, float, float]
Zoom = Annotated[int, Field(ge=0, le=30)]


class PackInfo(BaseModel):
    format: Literal[1] = 1  # this label's version number
    kind: Literal["state", "mission"]
    contents: Literal["basemap", "terrain"]
    name: str = Field(min_length=1)  # "Colorado", "Brainard Lake"
    file: str = Field(pattern=r"^[^/\\]+\.pmtiles$")  # a map file in this folder, not a path elsewhere
    area: list[Box] = Field(min_length=1)  # Alaska has two boxes, one each side of the 180° line
    min_zoom: Zoom
    max_zoom: Zoom
    source_urls: list[str]  # a mission pack can come from several files
    data_date: date | None  # how old the map data is; None when unknown
    downloaded: date
    bytes: int = Field(ge=0)  # the map file's size
    status: Literal["complete", "partial"]
