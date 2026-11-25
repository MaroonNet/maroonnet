"""Web routes for lost-person probability maps (spm predictions).

    GET  /api/spm/status                         can spm run, and which models and categories
    POST /api/spm/predict                        make a prediction; answers with its overlay
    GET  /api/spm/predictions                    every saved prediction, newest first
    GET  /api/spm/predictions/{id}/overlay.png   the picture to lay on the map
    POST /api/spm/predictions/{id}/update        re-weight it after sectors were searched

A prediction is drawn as a MapLibre image source: the PNG, placed by the four corner
coordinates in its overlay ("coordinates": top-left, top-right, bottom-right, bottom-left).
"""

import json
import os
import re
import subprocess
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.exc import OperationalError
from sqlmodel import Session

from mission.open_mission import get_open_mission
from missiondb import get_session
from missiondb.models import SectorStatus

from . import spm
from .sectors import sectors_geojson

router = APIRouter(prefix="/api/spm")

# Where predictions are kept. A prediction holds the point a real person was last seen, so the
# default sits under missions/, which git ignores everywhere.
PREDICTIONS_SETTING = "SPM_PREDICTIONS_DIR"
DEFAULT_PREDICTIONS_DIR = "missions/predictions"

# A prediction's id is its file name: a time stamp, the category, and the minutes since last seen if given.
# Nothing else is accepted, so an id can never name a file outside the folder.
PREDICTION_ID = re.compile(r"\d{8}-\d{6}_[a-z0-9_]+")

# One prediction at a time: each is a few seconds of one processor and up to 1 GB of memory.
_running = threading.Lock()


class PredictRequest(BaseModel):
    lon: float = Field(ge=-180, le=180)  # where the subject was last seen
    lat: float = Field(ge=-90, le=90)
    category: str = "hiker"
    model: str = "model_a"  # a file name under ml/spm/models, as /api/spm/status lists them
    elapsed_h: float | None = Field(default=None, ge=0, le=720)  # hours since last seen
    res: Literal[10, 20, 50, 100] = 20  # cell size of the map, metres


Pod = Annotated[float, Field(ge=0, le=1)]  # probability of detection


class UpdateRequest(BaseModel):
    """The POD of the sectors searched without a find. The mission database holds no POD yet,
    so the page sends it: one value for every sector, values for single sectors, or both."""

    pod: Pod | None = None
    pod_by_sector: dict[int, Pod] = {}  # sector id: POD; overrides pod for that sector
    statuses: list[SectorStatus] = [SectorStatus.COMPLETED]  # which sectors count as searched


def predictions_dir() -> Path:
    """The variable wins. Without it a prediction is kept with the open mission, in a
    `predictions` folder inside the mission's folder, so each mission shows only its own;
    with no mission open, the shared folder."""
    if override := os.environ.get(PREDICTIONS_SETTING):
        return Path(override).resolve()
    if (opened := get_open_mission()) is not None:
        return (opened.folder / "predictions").resolve()
    return Path(DEFAULT_PREDICTIONS_DIR).resolve()


def read_overlay(folder: Path, prediction_id: str) -> dict | None:
    """What the web app needs to draw one prediction, or None if its files are not there."""
    json_path = folder / f"{prediction_id}_overlay.json"
    if not (folder / f"{prediction_id}_overlay.png").is_file():
        return None
    try:
        overlay = json.loads(json_path.read_text())
    except (OSError, ValueError):
        return None
    overlay["id"] = prediction_id
    overlay["image"] = f"/api/spm/predictions/{prediction_id}/overlay.png"
    return overlay


@router.get("/status")
def status():
    root = spm.spm_dir()
    reason = spm.unavailable_reason(root)
    return {
        "available": reason is None,
        "detail": reason or "ok",
        "models": {} if reason else spm.models(root),  # model name: the categories it can draw
    }


@router.get("/predictions")
def list_predictions():
    folder = predictions_dir()
    ids = sorted((p.name.removesuffix("_overlay.json") for p in folder.glob("*_overlay.json")),
                 reverse=True)  # an id starts with its time stamp, so this is newest first
    overlays = (read_overlay(folder, i) for i in ids if PREDICTION_ID.fullmatch(i))
    return [overlay for overlay in overlays if overlay]


@router.get("/predictions/{prediction_id}/overlay.png")
def overlay_png(prediction_id: str):
    path = predictions_dir() / f"{prediction_id}_overlay.png"
    if not PREDICTION_ID.fullmatch(prediction_id) or not path.is_file():
        raise HTTPException(404, "no such prediction")
    return FileResponse(path, media_type="image/png")


@router.post("/predict")
def predict(request: PredictRequest):
    root = spm.spm_dir()
    if reason := spm.unavailable_reason(root):
        raise HTTPException(503, f"spm is not available: {reason}")
    models = spm.models(root)
    if request.model not in models:
        raise HTTPException(400, f"no model {request.model!r}; there is: {', '.join(models)}")
    categories = models[request.model]
    if request.category not in categories:
        raise HTTPException(
            400,
            f"{request.model} has no distance ring for {request.category!r}; "
            f"it covers: {', '.join(categories) or 'none'}",
        )

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    prediction_id = f"{stamp}_{request.category}"
    if request.elapsed_h is not None:
        prediction_id += f"_{round(request.elapsed_h * 60)}min"
    folder = predictions_dir()
    folder.mkdir(parents=True, exist_ok=True)
    args = [
        "predict", str(root / "models" / f"{request.model}.json"),
        "--ipp", f"{request.lon:.6f}", f"{request.lat:.6f}",
        "--category", request.category,
        "--res", str(request.res),
        "--out", str(folder / prediction_id),
    ]
    if request.elapsed_h is not None:
        args += ["--elapsed-h", f"{request.elapsed_h:g}"]

    return run_spm(root, args, folder, prediction_id)


@router.post("/predictions/{prediction_id}/update")
def update(prediction_id: str, request: UpdateRequest, session: Session = Depends(get_session)):
    """A new prediction: this one, with probability moved out of the searched sectors. The
    original is kept. Updating an update works too, for a second round of searching."""
    folder = predictions_dir()
    raster = folder / f"{prediction_id}.tif"
    if not PREDICTION_ID.fullmatch(prediction_id) or not raster.is_file():
        raise HTTPException(404, "no such prediction")
    root = spm.spm_dir()
    if reason := spm.unavailable_reason(root):
        raise HTTPException(503, f"spm is not available: {reason}")

    try:
        searched = sectors_geojson(
            session, request.pod, request.pod_by_sector, tuple(request.statuses)
        )
    except OperationalError:  # no such table: MISSIONDB_URL names a file that is not a mission
        raise HTTPException(
            503, "the mission database has no sectors table: check MISSIONDB_URL and run the migrations"
        )
    if not any("pod" in feature["properties"] for feature in searched["features"]):
        raise HTTPException(400, "no searched sector has a POD, so there is nothing to update")

    # Updates of one prediction are numbered: <id>_u1, <id>_u2, ...
    base = re.sub(r"_u\d+$", "", prediction_id)
    number = 1 + len(list(folder.glob(f"{base}_u*_overlay.json")))
    updated_id = f"{base}_u{number}"
    # Kept beside the result, as the record of which sectors and PODs went into it.
    searched_path = folder / f"{updated_id}_searched.geojson"
    searched_path.write_text(json.dumps(searched))
    args = ["update", str(raster), "--searched", str(searched_path),
            "--out", str(folder / updated_id)]
    return run_spm(root, args, folder, updated_id)


def run_spm(root: Path, args: list[str], folder: Path, prediction_id: str) -> dict:
    """Run one spm command that writes a prediction, and answer with its overlay."""
    command = f"spm {args[0]}"
    if not _running.acquire(blocking=False):
        raise HTTPException(409, "a prediction is already running")
    try:
        result = spm.run(root, args)
    except subprocess.TimeoutExpired:
        raise HTTPException(504, f"{command} took longer than {spm.TIMEOUT_S} s")
    except OSError as error:
        raise HTTPException(500, f"{command} could not start: {error}")
    finally:
        _running.release()

    if result.returncode != 0:
        print(f"{command} failed:\n{result.stderr[-2000:]}", flush=True)
        # A refusal is spm saying why it will not draw this map: the user needs to read it.
        if message := spm.refusal(result.stderr):
            raise HTTPException(422, message)
        raise HTTPException(500, f"{command} failed; see the backend's terminal")
    overlay = read_overlay(folder, prediction_id)
    if overlay is None:
        raise HTTPException(500, f"{command} wrote no overlay")
    return overlay
