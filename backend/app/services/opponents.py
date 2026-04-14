import logging

from backend.app.core.db import run_query
from backend.app.schemas.opponents import OpponentHistoryRow, OpponentOptionOut
from backend.app.services.common import canonical_opponent_key, extract_opponent_from_match_name
from backend.app.services.matches import fetch_matches_for_dropdown

logger = logging.getLogger(__name__)


def _result_from_diff(diff: float) -> str:
    if diff > 0:
        return "W"
    if diff < 0:
        return "L"
    return "D"


def list_opponents() -> list[OpponentOptionOut]:
    """
    Canonical grouped opponents list, aligned with get_related_match_ids logic.
    """
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
    stints_diff_map = {
        int(row["match_id"]): float(row["point_diff"])
        for _, row in stints_summary_df.iterrows()
    }

    out: list[OpponentOptionOut] = []
    grouped = data.sort_values(["match_date", "match_id"], ascending=[False, False]).groupby("opponent_key")
    for opp_key, grp in grouped:
        rows = grp.to_dict(orient="records")
        history: list[OpponentHistoryRow] = []
        for r in rows:
            mid = int(r["match_id"])
            point_diff = float(stints_diff_map.get(mid, 0.0))
            history.append(
                OpponentHistoryRow(
                    match_id=mid,
                    match_date=str(r.get("match_date")) if r.get("match_date") is not None else None,
                    match_name=r.get("match_name"),
                    final_score=None,
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
    logger.info("opponents.list grouped opponents=%s", len(out))
    return out
