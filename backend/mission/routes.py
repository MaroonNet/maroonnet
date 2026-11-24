"""The web routes for missions and sessions."""

from fastapi import APIRouter

from .files import MissionFacts, list_missions

router = APIRouter(prefix="/api")


@router.get("/missions")
def get_missions() -> list[MissionFacts]:
    return list_missions()
