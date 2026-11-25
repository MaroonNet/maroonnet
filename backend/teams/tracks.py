"""The tracks of the open mission: where each searcher radio has been.

A track is every position its radio reported in the open session, in time order. It is cut
into pieces where the radio changed group, so the map can draw each piece in the color of
the group the radio was in at that moment.
"""

from datetime import datetime

from pydantic import BaseModel
from sqlmodel import Session, select

from missiondb.models import Location, Team, TeamGroupAssignment, TeamKind


class TrackPiece(BaseModel):
    """A stretch of a track walked in one group, or in none."""

    group_id: int | None
    # Each point is (longitude, latitude), the order the map takes. A piece after the first
    # starts on the last point of the piece before it, so the line has no gap.
    points: list[tuple[float, float]]


class Track(BaseModel):
    radio_id: int
    pieces: list[TrackPiece]


# One stretch of a radio's time in a group: from when, until when (None: still in it), which group.
Stretch = tuple[datetime, datetime | None, int]


def list_tracks(db: Session) -> list[Track]:
    """The track of every searcher radio that has reported a position, by radio. The command
    post radio and a relay have none."""
    stretches: dict[int, list[Stretch]] = {}
    for row in db.exec(select(TeamGroupAssignment).order_by(TeamGroupAssignment.from_time, TeamGroupAssignment.assignment_id)):
        stretches.setdefault(row.team_id, []).append((row.from_time, row.to_time, row.search_group_id))

    # Only the four columns are read, not whole rows: a mission has thousands of positions.
    # The location table's key is (radio, time), so they come out already in this order.
    reports = db.exec(
        select(Location.team_id, Location.time, Location.lat, Location.lon)
        .join(Team, Team.team_id == Location.team_id)
        .where(Team.kind == TeamKind.SEARCHER)
        .order_by(Location.team_id, Location.time)
    )
    tracks: dict[int, Track] = {}
    for radio_id, time, lat, lon in reports:
        track = tracks.setdefault(radio_id, Track(radio_id=radio_id, pieces=[]))
        group_id = group_at(stretches.get(radio_id, []), time)
        point = (lon, lat)
        if not track.pieces:
            track.pieces.append(TrackPiece(group_id=group_id, points=[point]))
        elif track.pieces[-1].group_id != group_id:
            track.pieces.append(TrackPiece(group_id=group_id, points=[track.pieces[-1].points[-1], point]))
        else:
            track.pieces[-1].points.append(point)
    return list(tracks.values())


def group_at(stretches: list[Stretch], time: datetime) -> int | None:
    """The group a radio was in at this moment: its newest stretch that had started. The
    second a stretch ends still counts as in it, since ending a session closes every stretch
    at the session's end time. At the second a radio changes group, the new one has started,
    so it wins."""
    started = [stretch for stretch in stretches if stretch[0] <= time]
    if not started:
        return None
    _, until, group_id = started[-1]
    return group_id if until is None or time <= until else None
