"""Making a new mission: its folder, and the file of its first session."""

import re
import uuid
from pathlib import Path

from sqlmodel import Session

from missiondb import create_db_engine
from missiondb.migrate import upgrade
from missiondb.models import Mission, MissionStatus, Team
from teams.radio_list import read_radio_list

from .files import file_url
from .folders import missions_folder


def folder_name(name: str, mission_id: str) -> str:
    """The mission's folder: its name in lower case with a dash for whatever is not a
    letter or a digit, then the first part of its id, so two missions with the same name
    get two folders. "Bear Creek" becomes bear-creek-952592f8."""
    plain = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return f"{plain or 'mission'}-{mission_id[:8]}"


def session_file_name(session: int) -> str:
    return f"session-{session:02d}.sqlite3"


def create_mission(name: str, time_zone: str) -> Path:
    """Makes a mission in planning, with no start time, and answers with its folder. The
    file is brought to the current schema before the mission row is saved in it. The mission
    starts with every radio of the radio list, each with nobody on it."""
    radios = read_radio_list()
    mission_id = str(uuid.uuid4())
    folder = missions_folder() / folder_name(name, mission_id)
    folder.mkdir(parents=True)
    url = file_url(folder / session_file_name(1))
    upgrade(url)
    engine = create_db_engine(url)
    try:
        with Session(engine) as db:
            db.add(Mission(mission_id=1, mission_uuid=mission_id, name=name,
                           status=MissionStatus.PLANNING, time_zone=time_zone))
            # Numbered in the list's order, so the first listed radio is "Radio 1".
            for number, radio in enumerate(radios, start=1):
                db.add(Team(team_id=number, node_num=radio.node_num, kind=radio.kind))
            db.commit()
    finally:
        engine.dispose()
    return folder
