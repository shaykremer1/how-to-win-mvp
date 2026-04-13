from fastapi import APIRouter, Query

from backend.app.schemas.training import OpponentLineupsOut, ResponseVsLineupOut, TrainingOverviewOut
from backend.app.services.training import get_opponent_lineups, get_responses_vs_lineup, get_training_overview

router = APIRouter(prefix="/training", tags=["training"])


@router.get("/overview", response_model=TrainingOverviewOut)
def training_overview(
    match_id: int,
    overall_min_seconds: int = Query(default=180, ge=0),
    display_mode: str = "numbers",
):
    return get_training_overview(match_id, overall_min_seconds, display_mode)


@router.get("/opponent-lineups", response_model=OpponentLineupsOut)
def opponent_lineups(
    match_id: int,
    min_b_seconds: int = Query(default=120, ge=0),
):
    return get_opponent_lineups(match_id, min_b_seconds)


@router.get("/responses", response_model=ResponseVsLineupOut)
def responses_vs_lineup(
    match_id: int,
    b_key: str,
    min_resp_seconds: int = Query(default=60, ge=0),
    display_mode: str = "numbers",
):
    return get_responses_vs_lineup(match_id, b_key, min_resp_seconds, display_mode)
