"""The radio list: radios.json in the app data folder.

A temporary piece. How radios are added or paired is not decided, so until it is, the
radios a new mission starts with come from this file. Each entry is a node number and a kind:

    [
      {"node_num": 1296957441, "kind": "searcher"},
      {"node_num": 1296957447, "kind": "command_post"}
    ]

The file is meant to be edited by hand, for example to add a real test radio. The kinds are
searcher, command_post, relay and aerial.
"""

from pathlib import Path

from pydantic import BaseModel, Field, TypeAdapter

from maps.folders import app_data_folder
from missiondb.models import TeamKind

FILE_NAME = "radios.json"


class RadioEntry(BaseModel):
    node_num: int = Field(ge=0, le=0xFFFFFFFF)  # a Meshtastic node number: unsigned 32-bit
    kind: TeamKind


_entries = TypeAdapter(list[RadioEntry])

# Eight invented radios: six searchers, one command post, one relay. Their node numbers
# belong to no real radio.
FIRST_NODE_NUMBER = 1296957441
STARTING_KINDS = [TeamKind.SEARCHER] * 6 + [TeamKind.COMMAND_POST, TeamKind.RELAY]


def starting_radios() -> list[RadioEntry]:
    return [RadioEntry(node_num=FIRST_NODE_NUMBER + place, kind=kind) for place, kind in enumerate(STARTING_KINDS)]


def radio_list_path() -> Path:
    return app_data_folder() / FILE_NAME


def read_radio_list() -> list[RadioEntry]:
    """The listed radios, in the file's order. With no file, one is written with the eight
    invented radios. A damaged file is left as it is, so the hand edit can be corrected, and
    the invented radios are used, with a line printed to say so."""
    path = radio_list_path()
    if not path.exists():
        radios = starting_radios()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_entries.dump_json(radios, indent=2).decode("utf-8"), encoding="utf-8")
        return radios
    try:
        radios = _entries.validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:  # unreadable, cut off, or a kind that does not exist
        print(f"RADIOS {FILE_NAME} could not be read, so the invented radios are used: {error!r}", flush=True)
        return starting_radios()
    # A mission holds a node number once, so of two entries with one number the first stands.
    first_of_each = {radio.node_num: radio for radio in reversed(radios)}
    return [radio for radio in radios if first_of_each[radio.node_num] is radio]
