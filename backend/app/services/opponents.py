import csv
from pathlib import Path

from backend.app.core.db import run_query
from backend.app.schemas.opponents import OpponentHistoryRow, OpponentOptionOut
from backend.app.services.common import canonical_opponent_key, extract_opponent_from_match_name, infer_our_side_from_match_name
from backend.app.services.matches import fetch_matches_for_dropdown


def _result_from_diff(diff: float) -> str:
    if diff > 0:
        return "W"
    if diff < 0:
        return "L"
    return "D"


def _parse_score(score: str | None) -> tuple[int, int] | None:
    if not score or "-" not in score:
        return None
    try:
        left, right = score.split("-", 1)
        # Source feed score order is AWAY-HOME.
        away = int(left.strip())
        home = int(right.strip())
        return away, home
    except Exception:
        return None


def _score_our_perspective(score: str | None, our_side: str | None) -> str | None:
    parsed = _parse_score(score)
    if parsed is None:
        return None
    away, home = parsed
    if our_side == "away":
        return f"{away}-{home}"
    return f"{home}-{away}"


def _diff_from_score(score: str | None, our_side: str | None) -> float | None:
    parsed = _parse_score(score)
    if parsed is None:
        return None
    away, home = parsed
    if our_side == "away":
        return float(away - home)
    return float(home - away)


def _final_score_from_debug_csv(match_id: int) -> str | None:
    project_root = Path(__file__).resolve().parents[3]
    path = project_root / f"pbp_debug_{match_id}.csv"
    if not path.exists():
        return None

    last_score = None
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                score = (row.get("score") or "").strip()
                if "-" in score:
                    last_score = score
    except Exception:
        return None
    return last_score


def list_opponents() -> list[OpponentOptionOut]:
    matches_df = fetch_matches_for_dropdown()
    if matches_df.empty:
        return []

    data = matches_df.copy()
    data["opponent_name"] = data["match_name"].apply(extract_opponent_from_match_name)
    data = data[data["opponent_name"].notna()].copy()
    if data.empty:
        return []

    data["opponent_key"] = data["opponent_name"].apply(lambda x: canonical_opponent_key(str(x)))
    all_match_ids = data["match_id"].astype(int).tolist()

    stints_summary_df = run_query(
        """
        SELECT
            match_id,
            MIN(our_side) AS our_side,
            COALESCE(SUM(diff), 0) AS point_diff
        FROM stints
        WHERE match_id = ANY(%s::int[])
        GROUP BY match_id
        """,
        (all_match_ids,),
    )
    side_map = {
        int(row["match_id"]): str(row["our_side"]) if row["our_side"] is not None else None
        for _, row in stints_summary_df.iterrows()
    }
    stints_diff_map = {
        int(row["match_id"]): float(row["point_diff"])
        for _, row in stints_summary_df.iterrows()
    }

    out: list[OpponentOptionOut] = []
    grouped = data.sort_values(["match_date", "match_id"], ascending=[False, False]).groupby("opponent_key")
    for opp_key, grp in grouped:
        rows = grp.to_dict(orient="records")
        history = []
        for r in rows:
            mid = int(r["match_id"])
            our_side = side_map.get(mid) or infer_our_side_from_match_name(r.get("match_name"))
            raw_final_score = _final_score_from_debug_csv(mid)
            point_diff_from_score = _diff_from_score(raw_final_score, our_side)
            point_diff = (
                point_diff_from_score
                if point_diff_from_score is not None
                else float(stints_diff_map.get(mid, 0.0))
            )
            history.append(
                OpponentHistoryRow(
                    match_id=mid,
                    match_date=str(r.get("match_date")) if r.get("match_date") is not None else None,
                    match_name=r.get("match_name"),
                    final_score=_score_our_perspective(raw_final_score, our_side),
                    point_diff=point_diff,
                    result=_result_from_diff(point_diff),
                )
            )

        out.append(
            OpponentOptionOut(
                opponent_key=str(opp_key),
                opponent_name=str(rows[0]["opponent_name"]),
                sample_match_count=len(rows),
                representative_match_id=int(rows[0]["match_id"]),
                history=history,
            )
        )

    out.sort(key=lambda x: x.opponent_name)
    return out
