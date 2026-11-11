"""The map backend's web routes."""

import os

from fastapi import APIRouter, HTTPException, Path, Request, Response

from .packs import open_pack
from .style import build_style

router = APIRouter()

# Until the CPA has settings (plan phase 2), each pack's path comes from an environment variable.
BASEMAP_SETTING = "MAPS_BASEMAP_PACK"
TERRAIN_SETTING = "MAPS_TERRAIN_PACK"

Zoom = Path(ge=0, le=30)
Column = Path(ge=0)
Row = Path(ge=0)


def serve_tile(setting: str, z: int, x: int, y: int) -> Response:
    path = os.environ.get(setting)
    if not path:
        raise HTTPException(503, f"{setting} is not set")
    try:
        pack = open_pack(path)
    except FileNotFoundError:
        raise HTTPException(503, f"{setting} names a file that does not exist: {path}")
    data = pack.tile(z, x, y)
    if data is None:
        raise HTTPException(404, "the pack has no such tile")
    # Tiles are stored compressed. Content-Encoding tells the browser to unpack them itself.
    headers = {"Content-Encoding": pack.encoding} if pack.encoding else {}
    return Response(data, media_type=pack.media_type, headers=headers)


@router.get("/tiles/basemap/{z}/{x}/{y}")
def basemap_tile(z: int = Zoom, x: int = Column, y: int = Row):
    return serve_tile(BASEMAP_SETTING, z, x, y)


@router.get("/tiles/terrain/{z}/{x}/{y}")
def terrain_tile(z: int = Zoom, x: int = Column, y: int = Row):
    return serve_tile(TERRAIN_SETTING, z, x, y)


@router.get("/maps/style.json")
def style(request: Request):
    # The address this request came to, so the style points back at the same server.
    return build_style(str(request.base_url).rstrip("/"))
