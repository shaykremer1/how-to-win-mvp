from fastapi import APIRouter, Query

from backend.app.schemas.insights import TeamInsightsOut
from backend.app.services.insights import get_team_insights

router = APIRouter(prefix="/insights", tags=["insights"])


@router.get("/team", response_model=TeamInsightsOut)
def team_insights(
    match_id: int,
    overall_min_seconds: int = Query(default=180, ge=0),
    opponent_min_seconds: int = Query(default=120, ge=0),
    matchup_min_seconds: int = Query(default=60, ge=0),
    display_mode: str = "numbers",
    lineup_scope: str = Query(default="all", description="all | single — lineup tables only"),
    lineup_match_id: int | None = Query(default=None, description="When lineup_scope=single, filter to this game"),
):
    return get_team_insights(
        match_id=match_id,
        overall_min_seconds=overall_min_seconds,
        opponent_min_seconds=opponent_min_seconds,
        matchup_min_seconds=matchup_min_seconds,
        display_mode=display_mode,
        lineup_scope=lineup_scope,
        lineup_match_id=lineup_match_id,
    )
