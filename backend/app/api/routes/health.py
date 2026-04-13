from fastapi import APIRouter, HTTPException

from backend.app.core.db import check_connection

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
def health_live():
    """Process up (for load balancers). Does not hit the database."""
    return {"status": "alive"}


@router.get("")
def health():
    ok, err = check_connection()
    if not ok:
        raise HTTPException(status_code=503, detail={"status": "down", "error": err})
    return {"status": "ok"}
