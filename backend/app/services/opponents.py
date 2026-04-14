import logging

from backend.app.core.db import run_query
from backend.app.schemas.opponents import OpponentSimpleOut
from backend.app.services.common import extract_opponent_from_match_name

logger = logging.getLogger(__name__)


def list_opponents() -> list[OpponentSimpleOut]:
    """
    Simple, robust opponents list based only on matches_lookup.
    Returns one row per match.
    """
    df = run_query(
        """
        SELECT match_id, match_name, match_date
        FROM matches_lookup
        ORDER BY match_date DESC NULLS LAST, match_id DESC
        """
    )
    if df.empty:
        return []

    out: list[OpponentSimpleOut] = []
    for _, row in df.iterrows():
        match_name = row.get("match_name")
        opponent_name = extract_opponent_from_match_name(match_name)
        if not opponent_name:
            # fallback so endpoint still returns usable rows
            opponent_name = str(match_name).strip() if match_name is not None else f"Match #{int(row['match_id'])}"
        out.append(
            OpponentSimpleOut(
                opponent_name=str(opponent_name),
                match_id=int(row["match_id"]),
                match_date=str(row["match_date"]) if row.get("match_date") is not None else None,
            )
        )

    logger.info("opponents.list returned %s rows", len(out))
    return out
