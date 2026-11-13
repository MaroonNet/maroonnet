"""pack.json: the small file in each pack's folder that says what the pack is (spec 8.3)."""

import os
from datetime import date
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, Field, ValidationError

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


FILE_NAME = "pack.json"


def write_pack_info(folder: Path, info: PackInfo) -> None:
    """Writes folder/pack.json. The text goes to a temporary file first, which is then renamed
    over pack.json in one step, so the program stopping part way never leaves half a file."""
    temporary = folder / f"{FILE_NAME}.tmp"
    temporary.write_text(info.model_dump_json(indent=2), encoding="utf-8")
    os.replace(temporary, folder / FILE_NAME)


def read_pack_info(folder: Path) -> PackInfo | None:
    """Reads folder/pack.json. A missing or damaged one is skipped: this prints why and returns
    None, so one bad pack cannot stop the server."""
    try:
        return PackInfo.model_validate_json((folder / FILE_NAME).read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"Skipped {folder}: it has no {FILE_NAME}", flush=True)
    except (ValidationError, UnicodeDecodeError) as error:  # cut off, not text, or a wrong value
        print(f"Skipped {folder}: its {FILE_NAME} is damaged.\n{error}", flush=True)
    except OSError as error:  # for example, no permission to read it
        print(f"Skipped {folder}: its {FILE_NAME} could not be read ({error})", flush=True)
    return None
