from pydantic import BaseModel


class OpponentSimpleOut(BaseModel):
    opponent_name: str
    match_id: int
    match_date: str | None = None


class OpponentHistoryRow(BaseModel):
    match_id: int
    match_date: str | None = None
    match_name: str | None = None
    final_score: str | None = None
    point_diff: float = 0.0
    result: str = "N/A"


class OpponentOptionOut(BaseModel):
    opponent_key: str
    opponent_name: str
    sample_match_count: int
    representative_match_id: int
    history: list[OpponentHistoryRow]
