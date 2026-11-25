"""The web routes for waypoints.

    GET    /api/mission/waypoints       every waypoint on the open mission's map
    POST   /api/mission/waypoints       add one, placed by the commander
    PUT    /api/mission/waypoints/{id}  change one: its row is closed and a new row is added
    DELETE /api/mission/waypoints/{id}  take one off the map: its row is closed

A waypoint's row is never changed or deleted. Taking it off the map gives its row a
removed_time, and a change does that and adds a new row, so the after action report can
replay a waypoint appearing, moving and disappearing. The waypoints on the map are the rows
with no removed_time.

Any command post waypoint is the command post. A mission has one at a time, so saving a new
one closes the one before it.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlmodel import Session, select

from mission.open_mission import changeable_session, mission_session
from missiondb.models import Waypoint, WaypointType
from missiondb.sqltypes import utcnow

router = APIRouter(prefix="/api")

COMMAND_POST = "command_post"
# The database's limits. They are counted in bytes, since a waypoint's name and description
# are sized to fit a radio packet; an accented letter is two bytes.
NAME_BYTES = 30
DESCRIPTION_BYTES = 100


class Placing(BaseModel):
    """What the commander sets on a waypoint."""
    kind: str                       # a type_code of waypoint_type, such as "hazard"
    lat: float
    lon: float
    name: str
    description: str | None = None  # sent to teams with the waypoint, once sending is built
    note: str | None = None         # kept at the command post only


class WaypointFacts(Placing):
    id: int
    time: datetime              # when the thing happened or was seen
    created_time: datetime      # when this row was saved
    radio_id: int | None        # the radio that reported it, or none when the commander placed it


@router.get("/mission/waypoints")
def get_waypoints(db: Session = Depends(mission_session)) -> list[WaypointFacts]:
    on_map = select(Waypoint).where(Waypoint.removed_time.is_(None)).order_by(Waypoint.waypoint_id)
    return [facts(waypoint) for waypoint in db.exec(on_map)]


@router.post("/mission/waypoints", status_code=201)
def post_waypoint(placing: Placing, db: Session = Depends(changeable_session)) -> WaypointFacts:
    placing = checked(db, placing)
    now = utcnow()
    waypoint = Waypoint(type_code=placing.kind, lat=placing.lat, lon=placing.lon, time=now, created_time=now,
                        name=placing.name, description=placing.description, note=placing.note)
    return save(db, waypoint, now)


@router.put("/mission/waypoints/{waypoint_id}")
def put_waypoint(waypoint_id: int, placing: Placing, db: Session = Depends(changeable_session)) -> WaypointFacts:
    old = find(db, waypoint_id)
    placing = checked(db, placing)
    now = utcnow()
    moved = (placing.lat, placing.lon) != (old.lat, old.lon)
    # The new row keeps where the waypoint came from: when the thing was seen, and the radio
    # and message that reported it. Its elevation was measured at the old place.
    waypoint = Waypoint(type_code=placing.kind, lat=placing.lat, lon=placing.lon, time=old.time, created_time=now,
                        elevation=None if moved else old.elevation, team_id=old.team_id, message_id=old.message_id,
                        name=placing.name, description=placing.description, note=placing.note,
                        icon=old.icon, expire_time=old.expire_time)
    old.removed_time = now
    return save(db, waypoint, now)


@router.delete("/mission/waypoints/{waypoint_id}", status_code=204)
def delete_waypoint(waypoint_id: int, db: Session = Depends(changeable_session)) -> Response:
    find(db, waypoint_id).removed_time = utcnow()
    db.commit()
    return Response(status_code=204)


def find(db: Session, waypoint_id: int) -> Waypoint:
    waypoint = db.get(Waypoint, waypoint_id)
    if waypoint is None or waypoint.removed_time is not None:
        raise HTTPException(404, f"There is no waypoint {waypoint_id} on the map.")
    return waypoint


def checked(db: Session, placing: Placing) -> Placing:
    """The placing with its words tidied: no spaces around them, and empty words as none.
    Refuses one that breaks a rule of the database, with a line the screen can show."""
    name = placing.name.strip()
    description = (placing.description or "").strip() or None
    note = (placing.note or "").strip() or None
    if not name:
        raise HTTPException(422, "A waypoint needs a name.")
    if len(name.encode()) > NAME_BYTES:
        raise HTTPException(422, f"A waypoint's name holds {NAME_BYTES} bytes at most.")
    if description and len(description.encode()) > DESCRIPTION_BYTES:
        raise HTTPException(422, f"A waypoint's description holds {DESCRIPTION_BYTES} bytes at most.")
    if db.get(WaypointType, placing.kind) is None:
        raise HTTPException(422, f"There is no waypoint kind '{placing.kind}'.")
    if not (-90 <= placing.lat <= 90 and -180 <= placing.lon <= 180):
        raise HTTPException(422, "A waypoint must be on the map.")
    if placing.lat == 0 and placing.lon == 0:  # what a radio with no GPS fix reports
        raise HTTPException(422, "A waypoint cannot be at latitude 0, longitude 0.")
    return placing.model_copy(update={"name": name, "description": description, "note": note})


def save(db: Session, waypoint: Waypoint, now: datetime) -> WaypointFacts:
    """Saves a new row. A new command post closes the one that was on the map."""
    if waypoint.type_code == COMMAND_POST:
        earlier = select(Waypoint).where(Waypoint.type_code == COMMAND_POST, Waypoint.removed_time.is_(None))
        for command_post in db.exec(earlier):
            command_post.removed_time = now
    db.add(waypoint)
    db.commit()
    return facts(waypoint)


def facts(waypoint: Waypoint) -> WaypointFacts:
    return WaypointFacts(
        id=waypoint.waypoint_id, kind=waypoint.type_code, lat=waypoint.lat, lon=waypoint.lon, name=waypoint.name,
        description=waypoint.description, note=waypoint.note, time=waypoint.time,
        created_time=waypoint.created_time, radio_id=waypoint.team_id,
    )
