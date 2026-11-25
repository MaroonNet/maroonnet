"""The web routes for the search area.

    GET /api/mission/search-area   the open mission's search area, or nothing
    PUT /api/mission/search-area   set it; this replaces the one that was there
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, model_validator
from sqlmodel import Session, select

from mission.open_mission import changeable_session, mission_session
from missiondb.models import Mission, SearchArea

router = APIRouter(prefix="/api")

Latitude = Annotated[float, Field(ge=-90, le=90)]
Longitude = Annotated[float, Field(ge=-180, le=180)]


class SearchAreaFacts(BaseModel):
    """The rectangle's south-west and north-east corners, in degrees."""
    min_lat: Latitude
    min_lon: Longitude
    max_lat: Latitude
    max_lon: Longitude

    # The database's own rule for the corners (the "corners" check on search_area), checked
    # here first so a wrong rectangle is refused with a plain reason.
    @model_validator(mode="after")
    def corners_in_order(self):
        if not (self.min_lat < self.max_lat and self.min_lon < self.max_lon):
            raise ValueError("The south-west corner must be south and west of the north-east corner.")
        return self


@router.get("/mission/search-area")
def get_search_area(db: Session = Depends(mission_session)) -> SearchAreaFacts | None:
    # A mission has one search area at most. A new mission has none until one is drawn.
    area = db.exec(select(SearchArea)).first()
    if area is None:
        return None
    return SearchAreaFacts(min_lat=area.min_lat, min_lon=area.min_lon,
                           max_lat=area.max_lat, max_lon=area.max_lon)


@router.put("/mission/search-area")
def put_search_area(new: SearchAreaFacts, db: Session = Depends(changeable_session)) -> SearchAreaFacts:
    # A mission keeps one search area, so a new rectangle is written over the row that is
    # there. Only a mission with none yet gets a new row.
    area = db.exec(select(SearchArea)).first()
    if area is None:
        area = SearchArea(mission_id=db.exec(select(Mission.mission_id)).one())
    area.min_lat, area.min_lon = new.min_lat, new.min_lon
    area.max_lat, area.max_lon = new.max_lat, new.max_lon
    db.add(area)
    db.commit()
    return new
