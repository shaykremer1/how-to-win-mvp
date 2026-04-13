from backend.app.core.db import run_query
from backend.app.schemas.common import LineupCardOut
from backend.app.schemas.insights import MatchupInsightOut, TeamInsightsOut
from backend.app.services.common import format_lineup, get_related_match_ids
from backend.app.services.insights_lineup_table import compute_lineup_table, resolve_lineup_match_scope
from backend.app.services.matches import fetch_matches_for_dropdown
from queries import ALL_B_AGG_SQL, BEST_A_OVERALL_SQL


def get_team_insights(
    match_id: int,
    overall_min_seconds: int,
    opponent_min_seconds: int,
    matchup_min_seconds: int,
    display_mode: str,
    lineup_scope: str = "all",
    lineup_match_id: int | None = None,
) -> TeamInsightsOut:
    matches_df = fetch_matches_for_dropdown()
    related_match_ids = get_related_match_ids(match_id, matches_df)

    lineup_scope_ids = resolve_lineup_match_scope(
        related_match_ids,
        match_id,
        lineup_scope,
        lineup_match_id,
    )
    lineup_our, pbp_our = compute_lineup_table(
        lineup_scope_ids,
        int(overall_min_seconds),
        display_mode,
        "our",
    )
    lineup_opp, pbp_opp = compute_lineup_table(
        lineup_scope_ids,
        int(overall_min_seconds),
        display_mode,
        "opponent",
    )
    lineup_pbp = pbp_our or pbp_opp

    best_df = run_query(BEST_A_OVERALL_SQL, params=(related_match_ids, int(overall_min_seconds), 5))
    best_overall = [
        LineupCardOut(
            lineup=format_lineup(row["a_key"], display_mode),
            diff_total=float(row["diff_total"]),
            diff_per_min=float(row["diff_per_min"]),
            minutes=float(row["seconds_total"]) / 60,
        )
        for _, row in best_df.iterrows()
    ]

    opp_df = run_query(ALL_B_AGG_SQL, params=(related_match_ids, int(opponent_min_seconds)))
    toughest_opp = [
        LineupCardOut(
            lineup=str(row["b_key"]),
            diff_total=float(row["diff_total"]),
            diff_per_min=float(row["diff_per_min"]),
            minutes=float(row["seconds_total"]) / 60,
        )
        for _, row in opp_df.head(5).iterrows()
    ]

    matchup_df = run_query(
        """
        SELECT
            a_key,
            b_key,
            SUM(total_seconds) AS total_seconds,
            SUM(total_diff) AS total_diff,
            CASE
                WHEN SUM(total_seconds) > 0
                    THEN (SUM(total_diff)::float / SUM(total_seconds)) * 60.0
                ELSE 0
            END AS diff_per_min
        FROM matchup_summary
        WHERE match_id = ANY(%s::int[])
        GROUP BY a_key, b_key
        HAVING SUM(total_seconds) >= %s
        """,
        params=(related_match_ids, int(matchup_min_seconds)),
    )

    strongest = []
    weakest = []
    if not matchup_df.empty:
        strongest_df = matchup_df.sort_values(["diff_per_min", "total_seconds"], ascending=[False, False]).head(5)
        weakest_df = matchup_df.sort_values(["diff_per_min", "total_seconds"], ascending=[True, False]).head(5)

        strongest = [
            MatchupInsightOut(
                our_lineup=format_lineup(row["a_key"], display_mode),
                opponent_lineup=str(row["b_key"]),
                diff_total=float(row["total_diff"]),
                diff_per_min=float(row["diff_per_min"]),
                minutes=float(row["total_seconds"]) / 60,
            )
            for _, row in strongest_df.iterrows()
        ]
        weakest = [
            MatchupInsightOut(
                our_lineup=format_lineup(row["a_key"], display_mode),
                opponent_lineup=str(row["b_key"]),
                diff_total=float(row["total_diff"]),
                diff_per_min=float(row["diff_per_min"]),
                minutes=float(row["total_seconds"]) / 60,
            )
            for _, row in weakest_df.iterrows()
        ]

    return TeamInsightsOut(
        related_match_ids=related_match_ids,
        lineup_table_our=lineup_our,
        lineup_table_opponent=lineup_opp,
        lineup_table_pbp_available=lineup_pbp,
        best_overall_lineups=best_overall,
        toughest_opponent_lineups=toughest_opp,
        strongest_matchups=strongest,
        weakest_matchups=weakest,
    )
