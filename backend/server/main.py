from fastapi import FastAPI

from maps.routes import router as maps_router
from mapdb.routes import router as spm_router

app = FastAPI()
app.include_router(maps_router)
app.include_router(spm_router)

@app.get("/api/health")
def health():
    return {"status": "ok"}
