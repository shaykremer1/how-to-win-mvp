from pydantic import BaseModel, Field

from backend.app.schemas.common import LineupCardOut


class LiveRecommendationIn(BaseModel):
    match_id: int
    opponent_players: list[int] = Field(min_length=3, max_length=5)
    available_today: list[int] = Field(min_length=5)
    min_seconds: int = 90
    display_mode: str = "numbers"


class LiveRecommendationOut(BaseModel):
    selected_match_id: int
    related_match_ids: list[int]
    sample_match_count: int = 0
    previous_match_count: int = 0
    sample_context_message: str | None = None
    opponent_name: str | None = None
    chosen_b_key: str
    overlap: int
    input_n: int
    overlap_label: str | None = None
    used_fallback: bool = False
    debug: dict | None = None
    recommendations: list[LineupCardOut]
    not_recommended: LineupCardOut | None = None
