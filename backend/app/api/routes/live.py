from fastapi import APIRouter

from backend.app.schemas.live import LiveRecommendationIn, LiveRecommendationOut
from backend.app.services.live import get_available_players, get_live_recommendation

router = APIRouter(prefix="/live", tags=["live"])


@router.get("/available-players")
def available_players(match_id: int):
    return get_available_players(match_id)


@router.post("/recommendation", response_model=LiveRecommendationOut)
def recommend_lineup(payload: LiveRecommendationIn):
    return get_live_recommendation(payload)
