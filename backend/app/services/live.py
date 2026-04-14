from backend.app.core.db import run_query
from backend.app.schemas.common import LineupCardOut
from backend.app.schemas.live import LiveRecommendationIn, LiveRecommendationOut
from backend.app.services.common import PLAYER_MAP, extract_opponent_from_match_name, format_lineup, get_related_match_ids
from backend.app.services.matches import fetch_matches_for_dropdown


def _overlap_label(overlap: int, input_n: int) -> tuple[str, bool]:
    overlap = int(overlap or 0)
    input_n = int(input_n or 0)
    if input_n <= 0:
        return "No matchup quality available", False
    if overlap <= 0:
        return f"No reasonable matchup ({overlap}/{input_n})", False
    if overlap >= input_n:
        return f"Exact match ({overlap}/{input_n})", False
    if input_n == 5 and overlap == 4:
        return "Closest match (4/5)", True
    if input_n == 5 and overlap == 3:
        return "Closest match (3/5)", True
    return f"Closest match ({overlap}/{input_n})", True


def _parse_lineup_players(lineup_key: str) -> set[int]:
    out: set[int] = set()
    for token in str(lineup_key or "").split("-"):
        token = token.strip()
        if not token:
            continue
        try:
            out.add(int(token))
        except ValueError:
            continue
    return out


def _normalize_numbers(values: list[int]) -> list[int]:
    cleaned = []
    for v in values:
        try:
            n = int(v)
        except Exception:
            continue
        if n > 0:
            cleaned.append(n)
    return sorted(set(cleaned))


def _minimum_reasonable_overlap(input_n: int) -> int:
    # Keep fallback practical for 3-5 selected players.
    # 5 -> 3, 4 -> 2, 3 -> 2
    if input_n >= 5:
        return 3
    if input_n == 4:
        return 2
    if input_n == 3:
        return 2
    return max(1, input_n)


def _availability_label(available_count: int) -> tuple[str, str]:
    if available_count >= 5:
        return "Fully available lineup (5/5)", "full_5_of_5"
    if available_count == 4:
        return "Closest playable lineup (4/5)", "fallback_4_of_5"
    if available_count == 3:
        return "Partial fallback lineup (3/5)", "fallback_3_of_5"
    return f"Low-availability lineup ({available_count}/5)", "low_availability"


def get_available_players(match_id: int) -> dict:
    matches_df = fetch_matches_for_dropdown()
    related_match_ids = get_related_match_ids(match_id, matches_df)
    selected_row = matches_df[matches_df["match_id"] == match_id]
    match_name = selected_row.iloc[0]["match_name"] if not selected_row.empty else ""
    opponent_name = extract_opponent_from_match_name(match_name)

    df = run_query(
        """
        WITH players AS (
          SELECT a1 AS player FROM stints WHERE match_id = ANY(%s::int[])
          UNION
          SELECT a2 AS player FROM stints WHERE match_id = ANY(%s::int[])
          UNION
          SELECT a3 AS player FROM stints WHERE match_id = ANY(%s::int[])
          UNION
          SELECT a4 AS player FROM stints WHERE match_id = ANY(%s::int[])
          UNION
          SELECT a5 AS player FROM stints WHERE match_id = ANY(%s::int[])
        )
        SELECT DISTINCT player
        FROM players
        WHERE player IS NOT NULL
        ORDER BY player;
        """,
        (related_match_ids, related_match_ids, related_match_ids, related_match_ids, related_match_ids),
    )
    players = df["player"].astype(int).tolist() if not df.empty else []
    players_details = [
        {
            "number": p,
            "name": PLAYER_MAP.get(str(p)),
            "label_numbers": str(p),
            "label_names": PLAYER_MAP.get(str(p), str(p)),
            "label_both": f"{p} - {PLAYER_MAP.get(str(p), str(p))}",
        }
        for p in players
    ]

    opp_df = run_query(
        """
        WITH opponent_players AS (
          SELECT b1 AS player FROM stints WHERE match_id = ANY(%s::int[])
          UNION
          SELECT b2 AS player FROM stints WHERE match_id = ANY(%s::int[])
          UNION
          SELECT b3 AS player FROM stints WHERE match_id = ANY(%s::int[])
          UNION
          SELECT b4 AS player FROM stints WHERE match_id = ANY(%s::int[])
          UNION
          SELECT b5 AS player FROM stints WHERE match_id = ANY(%s::int[])
        )
        SELECT DISTINCT player
        FROM opponent_players
        WHERE player IS NOT NULL
        ORDER BY player;
        """,
        (related_match_ids, related_match_ids, related_match_ids, related_match_ids, related_match_ids),
    )
    opponent_players = opp_df["player"].astype(int).tolist() if not opp_df.empty else []
    opponent_players_details = [
        {
            "number": p,
            "label_numbers": str(p),
            "label_names": str(p),
            "label_both": str(p),
        }
        for p in opponent_players
    ]
    sample_count = len(related_match_ids)
    previous_count = max(sample_count - 1, 0)
    if previous_count > 0:
        sample_context_message = f"Based on {previous_count} previous games vs this opponent (total sample: {sample_count})."
    else:
        sample_context_message = "Based on 1 game vs this opponent (no previous meetings in database)."

    return {
        "match_id": match_id,
        "related_match_ids": related_match_ids,
        "sample_match_count": sample_count,
        "previous_match_count": previous_count,
        "sample_context_message": sample_context_message,
        "opponent_name": opponent_name,
        "players": players,
        "players_details": players_details,
        "opponent_players": opponent_players,
        "opponent_players_details": opponent_players_details,
    }


def get_live_recommendation(payload: LiveRecommendationIn) -> LiveRecommendationOut:
    matches_df = fetch_matches_for_dropdown()
    related_match_ids = get_related_match_ids(payload.match_id, matches_df)
    selected_row = matches_df[matches_df["match_id"] == payload.match_id]
    match_name = selected_row.iloc[0]["match_name"] if not selected_row.empty else ""
    opponent_name = extract_opponent_from_match_name(match_name)

    selected_opp = _normalize_numbers(payload.opponent_players)
    selected_available = _normalize_numbers(payload.available_today)
    selected_opp_set = set(selected_opp)
    selected_available_set = set(selected_available)
    input_n = len(selected_opp)
    min_overlap = _minimum_reasonable_overlap(input_n)

    stints_df = run_query(
        """
        SELECT
            a_lineup_key,
            b_lineup_key,
            time_played_seconds,
            diff
        FROM stints
        WHERE match_id = ANY(%s::int[])
          AND a_lineup_key IS NOT NULL
          AND b_lineup_key IS NOT NULL
        """,
        params=(related_match_ids,),
    )
    sample_count = len(related_match_ids)
    previous_count = max(sample_count - 1, 0)
    if previous_count > 0:
        sample_context_message = f"Based on {previous_count} previous games vs this opponent (total sample: {sample_count})."
    else:
        sample_context_message = "Based on 1 game vs this opponent (no previous meetings in database)."

    debug_info = {
        "selected_opponent_numbers": selected_opp,
        "selected_available_numbers": selected_available,
        "input_n": input_n,
        "min_overlap_threshold": min_overlap,
        "best_matched_observed_opponent_lineup": None,
        "computed_overlap_count": 0,
        "top_observed_overlap_candidates": [],
        "rejection_summary": {},
    }

    if stints_df.empty:
        quality_label, used_fallback = _overlap_label(0, input_n)
        return LiveRecommendationOut(
            selected_match_id=payload.match_id,
            related_match_ids=related_match_ids,
            sample_match_count=sample_count,
            previous_match_count=previous_count,
            sample_context_message=(
                sample_context_message
                + " No stints data found in the selected sample."
            ),
            opponent_name=opponent_name,
            chosen_b_key="",
            overlap=0,
            input_n=input_n,
            overlap_label=quality_label,
            used_fallback=used_fallback,
            availability_label="No playable lineup",
            availability_rule="none",
            available_in_chosen_lineup=0,
            unavailable_historical_players=[],
            debug=debug_info,
            recommendations=[],
            not_recommended=None,
        )

    b_group = (
        stints_df.groupby("b_lineup_key", as_index=False)["time_played_seconds"]
        .sum()
        .rename(columns={"time_played_seconds": "seconds_total"})
    )
    b_group["players_set"] = b_group["b_lineup_key"].apply(_parse_lineup_players)
    b_group["overlap"] = b_group["players_set"].apply(lambda s: len(s & selected_opp_set))

    if not b_group.empty:
        top_debug = b_group.sort_values(["overlap", "seconds_total"], ascending=[False, False]).head(8)
        debug_info["top_observed_overlap_candidates"] = [
            {
                "b_key": str(r["b_lineup_key"]),
                "overlap": int(r["overlap"]),
                "seconds_total": int(r["seconds_total"]),
            }
            for _, r in top_debug.iterrows()
        ]

    b_valid = b_group[b_group["overlap"] >= min_overlap].copy()
    rejected_by_overlap = max(len(b_group) - len(b_valid), 0)
    debug_info["rejection_summary"]["below_overlap_threshold"] = int(rejected_by_overlap)

    if b_valid.empty:
        quality_label, used_fallback = _overlap_label(0, input_n)
        return LiveRecommendationOut(
            selected_match_id=payload.match_id,
            related_match_ids=related_match_ids,
            sample_match_count=sample_count,
            previous_match_count=previous_count,
            sample_context_message=(
                sample_context_message
                + f" No usable matchup found with at least {min_overlap} overlapping opponent players."
            ),
            opponent_name=opponent_name,
            chosen_b_key="",
            overlap=0,
            input_n=input_n,
            overlap_label=quality_label,
            used_fallback=used_fallback,
            availability_label="No playable lineup",
            availability_rule="none",
            available_in_chosen_lineup=0,
            unavailable_historical_players=[],
            debug=debug_info,
            recommendations=[],
            not_recommended=None,
        )

    best_b = b_valid.sort_values(["overlap", "seconds_total", "b_lineup_key"], ascending=[False, False, True]).iloc[0]
    chosen_bkey = str(best_b["b_lineup_key"])
    overlap = int(best_b["overlap"])
    debug_info["best_matched_observed_opponent_lineup"] = chosen_bkey
    debug_info["computed_overlap_count"] = overlap

    chosen_rows = stints_df[stints_df["b_lineup_key"] == chosen_bkey].copy()

    a_agg = (
        chosen_rows.groupby("a_lineup_key", as_index=False)
        .agg(total_seconds=("time_played_seconds", "sum"), total_diff=("diff", "sum"))
    )
    a_agg = a_agg[a_agg["total_seconds"] >= int(payload.min_seconds)].copy()
    debug_info["rejection_summary"]["below_min_seconds"] = int(
        chosen_rows["a_lineup_key"].nunique() - a_agg["a_lineup_key"].nunique()
    )

    if not a_agg.empty:
        a_agg["players_set"] = a_agg["a_lineup_key"].apply(_parse_lineup_players)
        a_agg["available_count"] = a_agg["players_set"].apply(lambda s: len(s & selected_available_set))
        a_agg["unavailable_players"] = a_agg["players_set"].apply(lambda s: sorted(list(s - selected_available_set)))

    # Availability fallback tiers: 5/5 -> 4/5 -> 3/5
    tier_rows = a_agg[a_agg["available_count"] >= 5].copy() if not a_agg.empty else a_agg
    selected_availability_tier = 5
    if tier_rows.empty:
        tier_rows = a_agg[a_agg["available_count"] >= 4].copy() if not a_agg.empty else a_agg
        selected_availability_tier = 4
    if tier_rows.empty:
        tier_rows = a_agg[a_agg["available_count"] >= 3].copy() if not a_agg.empty else a_agg
        selected_availability_tier = 3

    debug_info["rejection_summary"]["below_availability_tier"] = int(
        max(len(a_agg) - len(tier_rows), 0)
    )

    if a_agg.empty or tier_rows.empty:
        quality_label, used_fallback = _overlap_label(overlap, input_n)
        return LiveRecommendationOut(
            selected_match_id=payload.match_id,
            related_match_ids=related_match_ids,
            sample_match_count=sample_count,
            previous_match_count=previous_count,
            sample_context_message=(
                sample_context_message
                + " Found opponent matchup, but no lineup met current filters and minimum availability (3/5)."
            ),
            opponent_name=opponent_name,
            chosen_b_key=chosen_bkey,
            overlap=overlap,
            input_n=input_n,
            overlap_label=quality_label,
            used_fallback=used_fallback,
            availability_label="No playable lineup",
            availability_rule="none",
            available_in_chosen_lineup=0,
            unavailable_historical_players=[],
            debug=debug_info,
            recommendations=[],
            not_recommended=None,
        )

    tier_rows["diff_per_min"] = tier_rows.apply(
        lambda r: (float(r["total_diff"]) / float(r["total_seconds"])) * 60.0 if float(r["total_seconds"]) > 0 else 0.0,
        axis=1,
    )
    tier_rows = tier_rows.sort_values(
        ["diff_per_min", "total_seconds", "a_lineup_key"], ascending=[False, False, True]
    )
    quality_label, used_fallback = _overlap_label(overlap, input_n)
    availability_label, availability_rule = _availability_label(selected_availability_tier)
    best_row = tier_rows.iloc[0]
    unavailable_players = [int(x) for x in (best_row["unavailable_players"] or [])]
    debug_info["selected_availability_tier"] = selected_availability_tier
    debug_info["selected_unavailable_players"] = unavailable_players

    recommendations = []
    for _, row in tier_rows.head(3).iterrows():
        recommendations.append(
            LineupCardOut(
                lineup=format_lineup(str(row["a_lineup_key"]), payload.display_mode),
                diff_total=float(row["total_diff"]),
                diff_per_min=float(row["diff_per_min"]),
                minutes=float(row["total_seconds"]) / 60.0,
            )
        )

    not_recommended = None
    if not tier_rows.empty:
        worst = tier_rows.sort_values(["diff_per_min", "total_seconds", "a_lineup_key"], ascending=[True, False, True]).iloc[0]
        not_recommended = LineupCardOut(
            lineup=format_lineup(str(worst["a_lineup_key"]), payload.display_mode),
            diff_total=float(worst["total_diff"]),
            diff_per_min=float(worst["diff_per_min"]),
            minutes=float(worst["total_seconds"]) / 60.0,
        )

    return LiveRecommendationOut(
        selected_match_id=payload.match_id,
        related_match_ids=related_match_ids,
        sample_match_count=sample_count,
        previous_match_count=previous_count,
        sample_context_message=sample_context_message,
        opponent_name=opponent_name,
        chosen_b_key=chosen_bkey,
        overlap=overlap,
        input_n=input_n,
        overlap_label=quality_label,
        used_fallback=used_fallback,
        availability_label=availability_label,
        availability_rule=availability_rule,
        available_in_chosen_lineup=selected_availability_tier,
        unavailable_historical_players=unavailable_players,
        debug=debug_info,
        recommendations=recommendations,
        not_recommended=not_recommended,
    )
