import logging

from backend.app.core.db import run_query
from backend.app.schemas.common import LineupCardOut
from backend.app.schemas.training import OpponentLineupsOut, ResponseVsLineupOut, TrainingOverviewOut
from backend.app.services.common import extract_opponent_from_match_name, format_lineup, get_related_match_ids
from backend.app.services.matches import fetch_matches_for_dropdown
from queries import ALL_B_AGG_SQL, BEST_A_OVERALL_SQL, VS_B_RESPONSES_SQL

logger = logging.getLogger(__name__)


def _context(match_id: int) -> tuple[list[int], str | None]:
    matches_df = fetch_matches_for_dropdown()
    related_match_ids = get_related_match_ids(match_id, matches_df)
    selected_row = matches_df[matches_df["match_id"] == match_id]
    match_name = selected_row.iloc[0]["match_name"] if not selected_row.empty else ""
    opponent_name = extract_opponent_from_match_name(match_name)
    return related_match_ids, opponent_name


def get_training_overview(match_id: int, overall_min_seconds: int, display_mode: str) -> TrainingOverviewOut:
    related_match_ids, opponent_name = _context(match_id)
    overall_df = run_query(BEST_A_OVERALL_SQL, params=(related_match_ids, int(overall_min_seconds), 1))

    best = None
    if not overall_df.empty:
        row = overall_df.iloc[0]
        best = LineupCardOut(
            lineup=format_lineup(row["a_key"], display_mode),
            diff_total=float(row["diff_total"]),
            diff_per_min=float(row["diff_per_min"]),
            minutes=float(row["seconds_total"]) / 60,
        )

    return TrainingOverviewOut(
        related_match_ids=related_match_ids,
        opponent_name=opponent_name,
        best_overall=best,
    )


def get_opponent_lineups(match_id: int, min_b_seconds: int) -> OpponentLineupsOut:
    related_match_ids, _ = _context(match_id)
    b_df = run_query(ALL_B_AGG_SQL, params=(related_match_ids, int(min_b_seconds)))

    lineups = [
        LineupCardOut(
            lineup=str(row["b_key"]),
            diff_total=float(row["diff_total"]),
            diff_per_min=float(row["diff_per_min"]),
            minutes=float(row["seconds_total"]) / 60,
        )
        for _, row in b_df.iterrows()
    ]
    return OpponentLineupsOut(related_match_ids=related_match_ids, lineups=lineups)


def get_responses_vs_lineup(
    match_id: int,
    b_key: str,
    min_resp_seconds: int,
    display_mode: str,
) -> ResponseVsLineupOut:
    related_match_ids, _ = _context(match_id)
    selected_b_summary = LineupCardOut(
        lineup=b_key,
        diff_total=0.0,
        diff_per_min=0.0,
        minutes=0.0,
    )
    message = None

    try:
        b_df = run_query(ALL_B_AGG_SQL, params=(related_match_ids, 0))
        if not b_df.empty:
            selected_rows = b_df[b_df["b_key"] == b_key]
            if not selected_rows.empty:
                chosen_row = selected_rows.iloc[0]
                selected_b_summary = LineupCardOut(
                    lineup=b_key,
                    diff_total=float(chosen_row["diff_total"]),
                    diff_per_min=float(chosen_row["diff_per_min"]),
                    minutes=float(chosen_row["seconds_total"]) / 60,
                )
            else:
                message = "Selected opponent lineup was not found in the aggregated sample."
                logger.warning(
                    "training.responses selected b_key missing | match_id=%s b_key=%s related_match_ids=%s",
                    match_id,
                    b_key,
                    related_match_ids,
                )
        else:
            message = "No opponent lineup data found for this match sample."
            logger.warning(
                "training.responses no opponent lineups | match_id=%s related_match_ids=%s",
                match_id,
                related_match_ids,
            )
    except Exception:
        message = "Failed to load opponent lineup summary."
        logger.exception(
            "training.responses failed ALL_B_AGG_SQL | match_id=%s b_key=%s related_match_ids=%s",
            match_id,
            b_key,
            related_match_ids,
        )

    try:
        resp_df = run_query(VS_B_RESPONSES_SQL, params=(related_match_ids, b_key, int(min_resp_seconds)))
    except Exception:
        logger.exception(
            "training.responses failed VS_B_RESPONSES_SQL | match_id=%s b_key=%s min_resp_seconds=%s related_match_ids=%s",
            match_id,
            b_key,
            min_resp_seconds,
            related_match_ids,
        )
        return ResponseVsLineupOut(
            related_match_ids=related_match_ids,
            selected_b_key=b_key,
            selected_b_summary=selected_b_summary,
            best_responses=[],
            message="Failed to load response lineups for selected opponent lineup.",
        )

    if resp_df.empty:
        if message is None:
            message = "No response lineups found under current sample and filters."
        return ResponseVsLineupOut(
            related_match_ids=related_match_ids,
            selected_b_key=b_key,
            selected_b_summary=selected_b_summary,
            best_responses=[],
            message=message,
        )

    best_responses = [
        LineupCardOut(
            lineup=format_lineup(row["a_key"], display_mode),
            diff_total=float(row["total_diff"]),
            diff_per_min=float(row["diff_per_min"]),
            minutes=float(row["total_seconds"]) / 60,
        )
        for _, row in resp_df.head(3).iterrows()
    ]

    return ResponseVsLineupOut(
        related_match_ids=related_match_ids,
        selected_b_key=b_key,
        selected_b_summary=selected_b_summary,
        best_responses=best_responses,
        message=message,
    )
