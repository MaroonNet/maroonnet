from fastapi import FastAPI

from maps.routes import router as maps_router

app = FastAPI()
app.include_router(maps_router)

@app.get("/api/health")
def health():
    return {"status": "ok"}
