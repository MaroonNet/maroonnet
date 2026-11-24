"""The map backend's web routes."""

import pathlib
import re

from fastapi import APIRouter, HTTPException, Path, Request, Response
from fastapi.responses import FileResponse

from .installed import packs_to_ask
from .style import build_style

router = APIRouter()

# Fonts and the icon sheet ship with the code, so the map needs nothing from the internet.
ASSETS = pathlib.Path(__file__).parent / "assets"

# Asset file names may use only letters, digits and . - _ @ (as in ofm@2x.png), and may not
# start with a dot. Any other name, such as "..\..\routes.py", could reach a file outside the
# folder: on Windows a backslash separates folders, the same way "/" does.
ASSET_NAME = re.compile(r"[A-Za-z0-9_@-][A-Za-z0-9._@-]*")


def is_asset_name(name: str) -> bool:
    return ASSET_NAME.fullmatch(name) is not None

Zoom = Path(ge=0, le=30)
Column = Path(ge=0)
Row = Path(ge=0)


def serve_tile(contents: str, z: int, x: int, y: int) -> Response:
    """Asks each installed basemap or terrain pack in turn. The first that has the tile answers."""
    for pack in packs_to_ask(contents):
        data = pack.tile(z, x, y)
        if data is not None:
            # Tiles are stored compressed. Content-Encoding tells the browser to unpack them itself.
            headers = {"Content-Encoding": pack.encoding} if pack.encoding else {}
            return Response(data, media_type=pack.media_type, headers=headers)
    raise HTTPException(404, "no installed pack has this tile")


def serve_asset(folder: str, name: str) -> FileResponse:
    file = ASSETS / folder / name
    if not is_asset_name(name) or not file.is_file():
        raise HTTPException(404, "no such file")
    return FileResponse(file)


@router.get("/tiles/basemap/{z}/{x}/{y}")
def basemap_tile(z: int = Zoom, x: int = Column, y: int = Row):
    return serve_tile("basemap", z, x, y)


@router.get("/tiles/terrain/{z}/{x}/{y}")
def terrain_tile(z: int = Zoom, x: int = Column, y: int = Row):
    return serve_tile("terrain", z, x, y)


# Used when no terrain pack is installed: a state pack's last zoom.
DEFAULT_TERRAIN_MAX_ZOOM = 12


def terrain_max_zoom() -> int:
    """The last zoom of the deepest installed terrain pack, read from each map file's own header.
    The map asks for terrain down to this zoom everywhere, so past a state pack's last zoom the
    hillshade and contours draw only inside a mission pack's box."""
    return max((pack.max_zoom for pack in packs_to_ask("terrain")), default=DEFAULT_TERRAIN_MAX_ZOOM)


@router.get("/maps/style.json")
def style(request: Request):
    # The address this request came to, so the style points back at the same server.
    return build_style(str(request.base_url).rstrip("/"), terrain_max_zoom())


@router.get("/maps/fonts/{name}")
def font(name: str):
    return serve_asset("fonts", name)


@router.get("/maps/sprites/{name}")
def sprite(name: str):
    return serve_asset("sprites", name)
