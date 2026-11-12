from fastapi import FastAPI
from pydantic import BaseModel

from maps.routes import router as maps_router

app = FastAPI()
app.include_router(maps_router)

@app.get("/api/health")
def health():
    return {"status": "ok"}


class ClientMessage(BaseModel):
    kind: str    # what went wrong: "error", "rejection" or "map"
    detail: str  # the error's message


# The web page sends its errors here, so they show in this terminal even where the
# browser's own tools are missing (inside the packaged app).
@app.post("/api/client-log", status_code=204)
def client_log(message: ClientMessage):
    print(f"CLIENT {message.kind}: {message.detail}", flush=True)
