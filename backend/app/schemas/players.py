from pydantic import BaseModel


class LeaderOut(BaseModel):
    stat: str
    player: str
    value: float | str


class PlayersAnalyticsOut(BaseModel):
    mode: str
    match_ids: list[int]
    columns: list[str]
    rows: list[dict]
    leaders: list[LeaderOut]
    calculation_note: str | None = None
