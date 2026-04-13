import subprocess
import sys

from pathlib import Path

from backend.app.core.db import run_exec, run_query
from backend.app.schemas.admin import ImportMatchIn, ImportMatchOut, MatchDataSummaryOut


def import_match(payload: ImportMatchIn) -> ImportMatchOut:
    project_root = Path(__file__).resolve().parents[3]
    script_path = str(project_root / "ingest_match.py")
    cmd = [
        sys.executable,
        script_path,
        str(int(payload.match_id)),
        "-",
        payload.manual_a.strip() if payload.manual_a and payload.manual_a.strip() else "-",
        payload.manual_b.strip() if payload.manual_b and payload.manual_b.strip() else "-",
    ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return ImportMatchOut(returncode=result.returncode, stdout=result.stdout or "", stderr=result.stderr or "")


def get_match_data_summary(match_id: int) -> MatchDataSummaryOut:
    meta_df = run_query(
        """
        SELECT match_id, match_name, match_date
        FROM matches_lookup
        WHERE match_id = %s
        """,
        (match_id,),
    )
    stints_count = int(run_query("SELECT COUNT(*) AS c FROM stints WHERE match_id = %s", (match_id,)).iloc[0]["c"])
    summary_count = int(
        run_query("SELECT COUNT(*) AS c FROM matchup_summary WHERE match_id = %s", (match_id,)).iloc[0]["c"]
    )

    match_name = None
    match_date = None
    if not meta_df.empty:
        row = meta_df.iloc[0]
        match_name = row.get("match_name")
        match_date = str(row.get("match_date")) if row.get("match_date") is not None else None

    return MatchDataSummaryOut(
        match_id=match_id,
        match_name=match_name,
        match_date=match_date,
        stints_count=stints_count,
        summary_count=summary_count,
    )


def delete_match_data(match_id: int) -> None:
    run_exec("DELETE FROM matchup_summary WHERE match_id = %s", (match_id,))
    run_exec("DELETE FROM stints WHERE match_id = %s", (match_id,))
    run_exec("DELETE FROM matches_lookup WHERE match_id = %s", (match_id,))
