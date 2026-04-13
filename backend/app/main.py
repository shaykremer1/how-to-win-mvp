import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.routes.admin import router as admin_router
from backend.app.api.routes.health import router as health_router
from backend.app.api.routes.insights import router as insights_router
from backend.app.api.routes.live import router as live_router
from backend.app.api.routes.matches import router as matches_router
from backend.app.api.routes.opponents import router as opponents_router
from backend.app.api.routes.players import router as players_router
from backend.app.api.routes.training import router as training_router
from backend.app.core.db import check_connection, validate_db_config_or_raise

app = FastAPI(
    title="How To Win API",
    version="0.1.0",
    description="Backend API for basketball lineup analytics.",
)


@app.on_event("startup")
def verify_db_on_startup() -> None:
    validate_db_config_or_raise()
    ok, err = check_connection()
    if not ok:
        raise RuntimeError(f"Database connection failed on startup: {err}")

def _cors_origins() -> list[str]:
    raw = os.getenv("CORS_ORIGINS", "").strip()
    if raw:
        out = [o.strip() for o in raw.split(",") if o.strip()]
        if out:
            return out
    return [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    ]


_cors_regex = os.getenv("CORS_ORIGIN_REGEX", "").strip() or None

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_origin_regex=_cors_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(matches_router)
app.include_router(opponents_router)
app.include_router(live_router)
app.include_router(training_router)
app.include_router(insights_router)
app.include_router(admin_router)
app.include_router(players_router)
