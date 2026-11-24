from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import FastAPI, Header
from pydantic import BaseModel

from maps.routes import router as maps_router
from mapdb.routes import router as spm_router
from mission.open_mission import mission_session, reopen_last_mission
from mission.routes import router as mission_router
from missiondb import get_session
from settings.routes import router as settings_router


# What runs once when the backend starts, before it answers any request.
@asynccontextmanager
async def lifespan(app: FastAPI):
    reopen_last_mission()
    yield


app = FastAPI(lifespan=lifespan)
app.include_router(maps_router)
app.include_router(spm_router)
app.include_router(settings_router)
app.include_router(mission_router)

# A route that asks missiondb for a database session (get_session) is handed one on the open
# mission in its place. The probability map routes ask this way, and so need no change.
app.dependency_overrides[get_session] = mission_session

@app.get("/api/health")
def health():
    return {"status": "ok"}


class ClientMessage(BaseModel):
    kind: str    # what went wrong: "error", "rejection", "map", "style" or "settings"
    detail: str  # the error's message


# The web page sends its errors here, so they show in this terminal even where the
# browser's own tools are missing (inside the packaged app). user_agent is the name the
# browser gives itself in every request, so each message says which browser sent it.
@app.post("/api/client-log", status_code=204)
def client_log(message: ClientMessage, user_agent: Annotated[str, Header()] = "unknown"):
    print(f"CLIENT {message.kind} from {user_agent}:\n{message.detail}", flush=True)
