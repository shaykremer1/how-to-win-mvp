from pydantic import BaseModel

from backend.app.schemas.common import LineupCardOut


class TrainingOverviewOut(BaseModel):
    related_match_ids: list[int]
    opponent_name: str | None = None
    best_overall: LineupCardOut | None = None


class OpponentLineupsOut(BaseModel):
    related_match_ids: list[int]
    lineups: list[LineupCardOut]


class ResponseVsLineupOut(BaseModel):
    related_match_ids: list[int]
    selected_b_key: str
    selected_b_summary: LineupCardOut
    best_responses: list[LineupCardOut]
    message: str | None = None
