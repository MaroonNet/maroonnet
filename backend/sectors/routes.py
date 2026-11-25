"""The web routes for sectors.

    GET    /api/mission/sectors               every sector of the open mission, with its corners
    POST   /api/mission/sectors               add one, drawn, named S and its number
    PUT    /api/mission/sectors/{id}/corners  change a never-assigned sector's shape
    DELETE /api/mission/sectors/{id}          delete a never-assigned sector

A sector is kept in two tables: search_sector for the sector, search_sector_point for its
corners, one row each. Adding or changing one writes both in the same transaction.
"""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field, model_validator
from sqlmodel import Session, delete, func, select

from mission.open_mission import changeable_session, mission_session
from missiondb.models import (
    SearchArea, SearchSector, SearchSectorPoint, SectorAssignment, SectorDispatch, SectorEntry,
    SectorStatus,
)
from missiondb.sqltypes import utcnow

from .shape import inside, sides_cross

router = APIRouter(prefix="/api")

Latitude = Annotated[float, Field(ge=-90, le=90)]
Longitude = Annotated[float, Field(ge=-180, le=180)]


class Corner(BaseModel):
    lat: Latitude
    lon: Longitude


class Shape(BaseModel):
    """A sector's corners, in order. The last joins back to the first. A sector is sent to
    the phones in one radio packet, which holds 3 to 24 corners."""
    corners: Annotated[list[Corner], Field(min_length=3, max_length=24)]

    @model_validator(mode="after")
    def sides_do_not_cross(self):
        if sides_cross(self.points()):
            raise ValueError("The sector's sides cannot cross.")
        return self

    def points(self) -> list[tuple[float, float]]:
        return [(corner.lat, corner.lon) for corner in self.corners]


class SectorFacts(BaseModel):
    id: int
    name: str                   # S and the id: "S4"
    status: SectorStatus        # drawn, searching, partial or completed
    corners: list[Corner]
    group_id: int | None        # the group that holds it now, or none
    can_edit: bool              # its shape can be changed and it can be deleted
    created_time: datetime
    completed_time: datetime | None


@router.get("/mission/sectors")
def get_sectors(db: Session = Depends(mission_session)) -> list[SectorFacts]:
    return [facts(db, sector) for sector in db.exec(select(SearchSector).order_by(SearchSector.search_sector_id))]


@router.post("/mission/sectors", status_code=201)
def post_sector(shape: Shape, db: Session = Depends(changeable_session)) -> SectorFacts:
    check_inside_search_area(db, shape)
    # The next number after the highest. Only a never-assigned sector can be deleted, so a
    # number used again after a delete was never sent to a radio.
    highest = db.exec(select(func.max(SearchSector.search_sector_id))).one() or 0
    number = highest + 1
    sector = SearchSector(search_sector_id=number, name=f"S{number}", status=SectorStatus.DRAWN,
                          created_time=utcnow())
    db.add(sector)
    add_corners(db, number, shape)
    db.commit()
    return facts(db, sector)


@router.put("/mission/sectors/{sector_id}/corners")
def put_corners(sector_id: int, shape: Shape, db: Session = Depends(changeable_session)) -> SectorFacts:
    sector = find(db, sector_id)
    if reason := locked_because(db, sector):
        raise HTTPException(409, f"{reason}, so its shape cannot be changed.")
    check_inside_search_area(db, shape)
    db.exec(delete(SearchSectorPoint).where(SearchSectorPoint.search_sector_id == sector_id))
    add_corners(db, sector_id, shape)
    db.commit()
    return facts(db, sector)


@router.delete("/mission/sectors/{sector_id}", status_code=204)
def delete_sector(sector_id: int, db: Session = Depends(changeable_session)) -> Response:
    sector = find(db, sector_id)
    if reason := locked_because(db, sector):
        raise HTTPException(409, f"{reason}, so it cannot be deleted.")
    # A radio may have passed through a sector nobody was given; that record goes with it.
    db.exec(delete(SectorEntry).where(SectorEntry.search_sector_id == sector_id))
    db.exec(delete(SearchSectorPoint).where(SearchSectorPoint.search_sector_id == sector_id))
    db.delete(sector)
    db.commit()
    return Response(status_code=204)


def find(db: Session, sector_id: int) -> SearchSector:
    sector = db.get(SearchSector, sector_id)
    if sector is None:
        raise HTTPException(404, f"There is no sector S{sector_id}.")
    return sector


def locked_because(db: Session, sector: SearchSector) -> str | None:
    """Why the sector's shape is fixed, or None while it can be changed and deleted. Once a
    sector has been given to a group it has been sent to the group's radios, and a sent
    sector is completed and replaced, never edited."""
    if sector.status == SectorStatus.COMPLETED:
        return f"{sector.name} is completed"
    sector_id = sector.search_sector_id
    assigned = db.exec(select(SectorAssignment).where(SectorAssignment.search_sector_id == sector_id)).first()
    sent = db.exec(select(SectorDispatch).where(SectorDispatch.search_sector_id == sector_id)).first()
    if assigned or sent:
        return f"{sector.name} has been assigned"
    # Assignments are not carried into the next session's file, so a sector searched in an
    # earlier session is known by its status.
    if sector.status != SectorStatus.DRAWN:
        return f"{sector.name} has been searched"
    return None


def check_inside_search_area(db: Session, shape: Shape) -> None:
    area = db.exec(select(SearchArea)).first()
    if area is None:
        raise HTTPException(409, "Draw a search area first.")
    if not inside(shape.points(), area):
        raise HTTPException(409, "A sector must be inside the search area.")


def add_corners(db: Session, sector_id: int, shape: Shape) -> None:
    for order, corner in enumerate(shape.corners, start=1):
        db.add(SearchSectorPoint(search_sector_id=sector_id, point_order=order, lat=corner.lat, lon=corner.lon))


def facts(db: Session, sector: SearchSector) -> SectorFacts:
    sector_id = sector.search_sector_id
    points = db.exec(select(SearchSectorPoint).where(SearchSectorPoint.search_sector_id == sector_id)
                     .order_by(SearchSectorPoint.point_order))
    holder = db.exec(select(SectorAssignment.search_group_id).where(
        SectorAssignment.search_sector_id == sector_id, SectorAssignment.to_time.is_(None))).first()
    return SectorFacts(
        id=sector_id, name=sector.name, status=sector.status,
        corners=[Corner(lat=point.lat, lon=point.lon) for point in points],
        group_id=holder, can_edit=locked_because(db, sector) is None,
        created_time=sector.created_time, completed_time=sector.completed_time,
    )


def sectors_outside(db: Session, area) -> list[str]:
    """The names of the saved sectors that would not be inside this search area."""
    outside = []
    for sector in db.exec(select(SearchSector).order_by(SearchSector.search_sector_id)):
        points = db.exec(select(SearchSectorPoint.lat, SearchSectorPoint.lon)
                         .where(SearchSectorPoint.search_sector_id == sector.search_sector_id)).all()
        if not inside(points, area):
            outside.append(sector.name)
    return outside
