from collections import defaultdict

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


def _availability_label(used_synthetic: bool, replaced_count: int) -> tuple[str, str]:
    if not used_synthetic:
        return "Fully available lineup (all 5 selected)", "full_5_of_5"
    if replaced_count <= 1:
        return "Closest playable lineup (1 replacement)", "fallback_replaced_1"
    return f"Partial fallback lineup ({replaced_count} replacements)", "fallback_replaced_multi"


def _lineup_key_from_players(players: list[int] | set[int]) -> str:
    xs = sorted({int(x) for x in players if int(x) > 0})
    return "-".join(str(x) for x in xs)


def _compute_available_player_scores(chosen_rows, selected_available_set: set[int]) -> dict[int, float]:
    sec_sum: dict[int, int] = defaultdict(int)
    diff_sum: dict[int, float] = defaultdict(float)
    for _, row in chosen_rows.iterrows():
        sec = int(row.get("time_played_seconds") or 0)
        diff = float(row.get("diff") or 0.0)
        players = _parse_lineup_players(row.get("a_lineup_key"))
        for p in players:
            if p in selected_available_set:
                sec_sum[p] += sec
                diff_sum[p] += diff
    scores: dict[int, float] = {}
    for p in selected_available_set:
        s = sec_sum.get(p, 0)
        scores[p] = (diff_sum.get(p, 0.0) / s) * 60.0 if s > 0 else 0.0
    return scores


def _synthesize_playable_lineup(
    players_set: set[int],
    selected_available_set: set[int],
    player_scores: dict[int, float],
    prefer_best: bool,
) -> tuple[str, list[int], list[dict], list[int]]:
    kept = sorted(players_set & selected_available_set)
    unavailable = sorted(players_set - selected_available_set)

    needed = max(0, 5 - len(kept))
    pool = sorted(selected_available_set - set(kept))
    if prefer_best:
        ranked = sorted(pool, key=lambda p: (-player_scores.get(p, 0.0), p))
    else:
        ranked = sorted(pool, key=lambda p: (player_scores.get(p, 0.0), p))

    substitutes = ranked[:needed]
    final_players = sorted(set(kept) | set(substitutes))
    if len(final_players) < 5:
        for p in ranked[needed:]:
            if p not in final_players:
                final_players.append(p)
            if len(final_players) >= 5:
                break
        final_players = sorted(final_players)

    replacements = []
    for i, out_p in enumerate(unavailable):
        replacements.append(
            {
                "replaced_unavailable_player": int(out_p),
                "replacement_player": int(substitutes[i]) if i < len(substitutes) else None,
            }
        )

    return _lineup_key_from_players(final_players), final_players, replacements, unavailable


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
            match_id,
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
    sample_ids = [int(x) for x in related_match_ids]
    sample_count = len(sample_ids)
    previous_ids = [mid for mid in sample_ids if int(mid) != int(payload.match_id)]
    previous_count = len(previous_ids)
    if previous_count > 0:
        sample_context_message = (
            f"Based on {sample_count} games in selected opponent sample. "
            f"Previous meetings before selected game: {previous_count}."
        )
    else:
        sample_context_message = (
            f"Based on {sample_count} game in selected opponent sample. "
            "No previous meetings before selected game."
        )

    debug_info = {
        "selected_opponent_numbers": selected_opp,
        "selected_available_numbers": selected_available,
        "related_match_ids_used": sample_ids,
        "total_sample_game_ids": sample_ids,
        "previous_meeting_ids_used": previous_ids,
        "input_n": input_n,
        "min_overlap_threshold": min_overlap,
        "best_matched_observed_opponent_lineup": None,
        "matched_opponent_lineup_source_match_ids": [],
        "candidate_our_lineup_source_match_ids": {},
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
    debug_info["matched_opponent_lineup_source_match_ids"] = sorted(
        {int(x) for x in chosen_rows["match_id"].dropna().tolist()}
    )

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
        a_agg["playable_full"] = a_agg["players_set"].apply(lambda s: s.issubset(selected_available_set))
        a_agg["source_match_ids"] = a_agg["a_lineup_key"].apply(
            lambda k: sorted(
                {int(x) for x in chosen_rows[chosen_rows["a_lineup_key"] == k]["match_id"].dropna().tolist()}
            )
        )

    full_rows = a_agg[a_agg["playable_full"]].copy() if not a_agg.empty else a_agg
    fallback_rows = a_agg[a_agg["available_count"] >= 3].copy() if not a_agg.empty else a_agg

    debug_info["rejection_summary"]["below_availability_tier"] = int(
        max(len(a_agg) - len(fallback_rows), 0)
    )
    debug_info["rejection_summary"]["not_fully_playable"] = int(max(len(a_agg) - len(full_rows), 0))

    if a_agg.empty or fallback_rows.empty:
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

    source_rows = full_rows if not full_rows.empty else fallback_rows
    source_rows = source_rows.copy()
    source_rows["diff_per_min"] = source_rows.apply(
        lambda r: (float(r["total_diff"]) / float(r["total_seconds"])) * 60.0 if float(r["total_seconds"]) > 0 else 0.0,
        axis=1,
    )
    source_rows = source_rows.sort_values(
        ["diff_per_min", "total_seconds", "a_lineup_key"], ascending=[False, False, True]
    )
    use_synthetic = full_rows.empty
    player_scores = _compute_available_player_scores(chosen_rows, selected_available_set)

    quality_label, used_fallback = _overlap_label(overlap, input_n)
    best_row = source_rows.iloc[0]
    if use_synthetic:
        best_lineup_key, _, best_replacements, unavailable_players = _synthesize_playable_lineup(
            set(best_row["players_set"]),
            selected_available_set,
            player_scores,
            prefer_best=True,
        )
    else:
        best_lineup_key = str(best_row["a_lineup_key"])
        best_replacements = []
        unavailable_players = []
    availability_label, availability_rule = _availability_label(use_synthetic, len(unavailable_players))
    debug_info["selected_unavailable_players"] = unavailable_players
    debug_info["chosen_replacements"] = best_replacements

    recommendations = []
    returned_lineups_debug = []
    for _, row in source_rows.head(3).iterrows():
        if use_synthetic:
            out_key, _, replacements, row_unavail = _synthesize_playable_lineup(
                set(row["players_set"]),
                selected_available_set,
                player_scores,
                prefer_best=True,
            )
        else:
            out_key = str(row["a_lineup_key"])
            replacements = []
            row_unavail = []
        recommendations.append(
            LineupCardOut(
                lineup=format_lineup(out_key, payload.display_mode),
                diff_total=float(row["total_diff"]),
                diff_per_min=float(row["diff_per_min"]),
                minutes=float(row["total_seconds"]) / 60.0,
            )
        )
        returned_lineups_debug.append(
            {
                "historical_lineup": str(row["a_lineup_key"]),
                "returned_lineup": out_key,
                "returned_lineup_players": [int(x) for x in out_key.split("-") if x],
                "source_match_ids": [int(x) for x in (row["source_match_ids"] or [])],
                "unavailable_historical_players": [int(x) for x in row_unavail],
                "replacements": replacements,
            }
        )
    debug_info["returned_lineups"] = returned_lineups_debug
    debug_info["candidate_our_lineup_source_match_ids"] = {
        str(row["a_lineup_key"]): [int(x) for x in (row["source_match_ids"] or [])]
        for _, row in source_rows.iterrows()
    }

    not_recommended = None
    if not source_rows.empty:
        worst = source_rows.sort_values(["diff_per_min", "total_seconds", "a_lineup_key"], ascending=[True, False, True]).iloc[0]
        if use_synthetic:
            worst_key, _, worst_replacements, _ = _synthesize_playable_lineup(
                set(worst["players_set"]),
                selected_available_set,
                player_scores,
                prefer_best=False,
            )
            debug_info["bad_lineup_replacements"] = worst_replacements
        else:
            worst_key = str(worst["a_lineup_key"])
        not_recommended = LineupCardOut(
            lineup=format_lineup(worst_key, payload.display_mode),
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
        available_in_chosen_lineup=5 if recommendations else 0,
        unavailable_historical_players=unavailable_players,
        debug=debug_info,
        recommendations=recommendations,
        not_recommended=not_recommended,
    )
