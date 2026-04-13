from pydantic import BaseModel


class MatchOut(BaseModel):
    match_id: int
    match_name: str | None = None
    match_date: str | None = None
    label: str


class LineupCardOut(BaseModel):
    lineup: str
    diff_total: float
    diff_per_min: float
    minutes: float
