from pydantic import BaseModel


class ImportMatchIn(BaseModel):
    match_id: int
    manual_a: str | None = None
    manual_b: str | None = None


class ImportMatchOut(BaseModel):
    returncode: int
    stdout: str
    stderr: str


class MatchDataSummaryOut(BaseModel):
    match_id: int
    match_name: str | None = None
    match_date: str | None = None
    stints_count: int
    summary_count: int
