from fastapi import APIRouter

from backend.app.schemas.opponents import OpponentOptionOut
from backend.app.services.opponents import list_opponents

router = APIRouter(prefix="/opponents", tags=["opponents"])


@router.get("", response_model=list[OpponentOptionOut])
def opponents():
    return list_opponents()
