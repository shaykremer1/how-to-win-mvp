from pydantic import BaseModel

from backend.app.schemas.common import LineupCardOut


class LineupTableRowOut(BaseModel):
    lineup_key: str
    lineup_display: str
    player_numbers: list[str]
    minutes: float
    pts_for: float | None = None
    pts_against: float | None = None
    fg2_attempts: int = 0
    fg3_attempts: int = 0
    plus_minus: float
    efficiency: float
    pbp_metrics_available: bool = False


class MatchupInsightOut(BaseModel):
    our_lineup: str
    opponent_lineup: str
    diff_total: float
    diff_per_min: float
    minutes: float


class TeamInsightsOut(BaseModel):
    related_match_ids: list[int]
    lineup_table_our: list[LineupTableRowOut] = []
    lineup_table_opponent: list[LineupTableRowOut] = []
    lineup_table_pbp_available: bool = False
    best_overall_lineups: list[LineupCardOut]
    toughest_opponent_lineups: list[LineupCardOut]
    strongest_matchups: list[MatchupInsightOut]
    weakest_matchups: list[MatchupInsightOut]
