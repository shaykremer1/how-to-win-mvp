from fastapi import APIRouter

from backend.app.schemas.players import PlayersAnalyticsOut
from backend.app.services.players import get_players_analytics
from backend.app.services.players import get_single_game_columns, get_single_game_players

router = APIRouter(prefix="/players", tags=["players"])


@router.get("/analytics", response_model=PlayersAnalyticsOut)
def players_analytics(
    mode: str = "single",
    match_id: int | None = None,
):
    return get_players_analytics(mode=mode, match_id=match_id)


@router.get("/boxscore/{match_id}")
def boxscore(match_id: int):
    return {
        "match_id": match_id,
        "columns": get_single_game_columns(match_id),
        "rows": get_single_game_players(match_id),
    }
