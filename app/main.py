from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api import auth, health, imports, keys, summary, sync
from app.database import init_db
from app.seed import seed_providers

app = FastAPI(title="Fusion Health", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://127.0.0.1:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    init_db()
    seed_providers()


app.mount("/static", StaticFiles(directory="dashboard"), name="static")


@app.get("/", include_in_schema=False)
def dashboard() -> FileResponse:
    return FileResponse("dashboard/index.html")


app.include_router(health.router)
app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(keys.router, prefix="/api/v1/api-keys", tags=["api keys"])
app.include_router(sync.router, prefix="/api/v1/sync", tags=["sync"])
app.include_router(summary.router, prefix="/api/v1", tags=["health data"])
app.include_router(imports.router, prefix="/api/v1/import", tags=["imports"])
