import logging

from fastapi import APIRouter, HTTPException

from backend.app.schemas.opponents import OpponentSimpleOut
from backend.app.services.opponents import list_opponents

router = APIRouter(prefix="/opponents", tags=["opponents"])
logger = logging.getLogger(__name__)


@router.get("", response_model=list[OpponentSimpleOut])
def opponents():
    try:
        return list_opponents()
    except Exception as e:
        logger.exception("opponents endpoint failed")
        raise HTTPException(status_code=500, detail=f"Failed to load opponents: {e}")
