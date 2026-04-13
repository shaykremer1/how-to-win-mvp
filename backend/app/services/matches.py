import pandas as pd

from backend.app.core.db import run_query


def fetch_matches_for_dropdown() -> pd.DataFrame:
    return run_query(
        """
        WITH ids_from_lookup AS (
            SELECT match_id, match_name, match_date
            FROM matches_lookup
        ),
        ids_from_stints AS (
            SELECT DISTINCT match_id
            FROM stints
        ),
        merged AS (
            SELECT match_id, match_name, match_date
            FROM ids_from_lookup
            UNION ALL
            SELECT s.match_id, NULL::text, NULL::date
            FROM ids_from_stints s
            WHERE NOT EXISTS (
                SELECT 1 FROM ids_from_lookup l WHERE l.match_id = s.match_id
            )
        )
        SELECT DISTINCT match_id, match_name, match_date
        FROM merged
        ORDER BY match_date DESC NULLS LAST, match_id DESC;
        """
    )


def make_match_label(row) -> str:
    mid = int(row["match_id"])
    name = row.get("match_name", None)
    mdate = row.get("match_date", None)

    date_part = ""
    if pd.notna(mdate):
        date_part = pd.to_datetime(mdate).strftime("%d/%m/%Y") + " | "

    if pd.isna(name) or not str(name).strip():
        return f"{date_part}Match #{mid}"
    return f"{date_part}{name} (#{mid})"
