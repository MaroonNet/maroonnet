"""The web routes for the search area.

    GET /api/mission/search-area   the open mission's search area, or nothing
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session, select

from mission.open_mission import mission_session
from missiondb.models import SearchArea

router = APIRouter(prefix="/api")


class SearchAreaFacts(BaseModel):
    """The rectangle's south-west and north-east corners, in degrees."""
    min_lat: float
    min_lon: float
    max_lat: float
    max_lon: float


@router.get("/mission/search-area")
def get_search_area(db: Session = Depends(mission_session)) -> SearchAreaFacts | None:
    # A mission has one search area at most. A new mission has none until one is drawn.
    area = db.exec(select(SearchArea)).first()
    if area is None:
        return None
    return SearchAreaFacts(min_lat=area.min_lat, min_lon=area.min_lon,
                           max_lat=area.max_lat, max_lon=area.max_lon)
