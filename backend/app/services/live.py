from backend.app.core.db import run_query
from backend.app.schemas.common import LineupCardOut
from backend.app.schemas.live import LiveRecommendationIn, LiveRecommendationOut
from backend.app.services.common import PLAYER_MAP, extract_opponent_from_match_name, format_lineup, get_related_match_ids
from backend.app.services.matches import fetch_matches_for_dropdown
from backend.app.core.queries import RECO_SQL


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

    df = run_query(
        RECO_SQL,
        params=(
            payload.opponent_players,
            related_match_ids,
            related_match_ids,
            payload.available_today,
            int(payload.min_seconds),
        ),
    )
    sample_count = len(related_match_ids)
    previous_count = max(sample_count - 1, 0)
    if previous_count > 0:
        sample_context_message = f"Based on {previous_count} previous games vs this opponent (total sample: {sample_count})."
    else:
        sample_context_message = "Based on 1 game vs this opponent (no previous meetings in database)."

    if df.empty:
        quality_label, used_fallback = _overlap_label(0, len(payload.opponent_players))
        return LiveRecommendationOut(
            selected_match_id=payload.match_id,
            related_match_ids=related_match_ids,
            sample_match_count=sample_count,
            previous_match_count=previous_count,
            sample_context_message=(
                sample_context_message
                + " No usable matchup found with at least 3 overlapping opponent players."
            ),
            opponent_name=opponent_name,
            chosen_b_key="",
            overlap=0,
            input_n=len(payload.opponent_players),
            overlap_label=quality_label,
            used_fallback=used_fallback,
            recommendations=[],
            not_recommended=None,
        )

    chosen_bkey = str(df["b_key"].iloc[0])
    overlap = int(df["chosen_overlap"].iloc[0])
    input_n = int(df["input_n"].iloc[0])
    quality_label, used_fallback = _overlap_label(overlap, input_n)

    show = df[["flag", "a_key", "total_seconds", "total_diff", "diff_per_min"]].copy()
    show["minutes"] = (show["total_seconds"] / 60).round(2)
    show["a_key"] = show["a_key"].apply(lambda x: format_lineup(x, payload.display_mode))

    recommendations = []
    not_recommended = None

    for _, row in show.iterrows():
        card = LineupCardOut(
            lineup=str(row["a_key"]),
            diff_total=float(row["total_diff"]),
            diff_per_min=float(row["diff_per_min"]),
            minutes=float(row["minutes"]),
        )
        if row["flag"] == "GREEN":
            recommendations.append(card)
        elif row["flag"] == "RED":
            not_recommended = card

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
        recommendations=recommendations,
        not_recommended=not_recommended,
    )
