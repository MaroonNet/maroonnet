from typing import Annotated

from fastapi import FastAPI, Header
from pydantic import BaseModel

from maps.routes import router as maps_router

app = FastAPI()
app.include_router(maps_router)

@app.get("/api/health")
def health():
    return {"status": "ok"}


class ClientMessage(BaseModel):
    kind: str    # what went wrong: "error", "rejection", "map" or "style"
    detail: str  # the error's message


# The web page sends its errors here, so they show in this terminal even where the
# browser's own tools are missing (inside the packaged app). user_agent is the name the
# browser gives itself in every request, so each message says which browser sent it.
@app.post("/api/client-log", status_code=204)
def client_log(message: ClientMessage, user_agent: Annotated[str, Header()] = "unknown"):
    print(f"CLIENT {message.kind} from {user_agent}:\n{message.detail}", flush=True)
