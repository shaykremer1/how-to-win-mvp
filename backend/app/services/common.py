import re

import pandas as pd

PLAYER_MAP = {
    "1": "כהן",
    "2": "פאק",
    "5": "היל",
    "6": "שפריר",
    "7": "שטורברג",
    "9": "שלף",
    "11": "שריוט",
    "15": "קלר",
    "16": "דקל",
    "18": "משען",
    "23": "זומרפלד",
    "25": "קוליה",
    "33": "שאול",
}

OUR_TEAM_ALIASES = {
    "עוטף דרום",
    "מ.כ. עוטף דרום",
    "מ.כ עוטף דרום",
}

OPPONENT_CANONICAL_ALIASES = {
    "א.ס. אשקלון/קרית גת": {
        "א.ס. אשקלון/קרית גת",
        "א.ס אשקלון/קרית גת",
        "א.ס. אשקלון / קרית גת",
        "א.ס אשקלון / קרית גת",
        "א.ס. אשקלון/קריית גת",
        "א.ס אשקלון/קריית גת",
        "א.ס. אשקלון / קריית גת",
        "א.ס אשקלון / קריית גת",
    },
}


def normalize_team_name(s: str) -> str:
    s = str(s or "").strip()
    s = re.sub(r"\s+", " ", s)
    s = s.replace("’", "'").replace("־", "-").replace("–", "-")
    return s


def _simple_team_key(name: str) -> str:
    txt = normalize_team_name(name).lower()
    txt = re.sub(r"[\"'׳״.\-_/]", " ", txt)
    txt = re.sub(r"\s+", " ", txt).strip()
    return txt


def canonical_opponent_key(name: str | None) -> str:
    if not name:
        return ""
    target = _simple_team_key(name)
    for canonical, variants in OPPONENT_CANONICAL_ALIASES.items():
        expanded = {_simple_team_key(canonical)} | {_simple_team_key(v) for v in variants}
        if target in expanded:
            return _simple_team_key(canonical)
    return target


def is_our_team_name(name: str) -> bool:
    normalized_aliases = {normalize_team_name(x) for x in OUR_TEAM_ALIASES}
    return normalize_team_name(name) in normalized_aliases


def extract_opponent_from_match_name(match_name: str) -> str | None:
    txt = normalize_team_name(match_name)
    if "נגד" not in txt:
        return None

    left, right = [normalize_team_name(x) for x in txt.split("נגד", 1)]
    if is_our_team_name(left) and not is_our_team_name(right):
        return right
    if is_our_team_name(right) and not is_our_team_name(left):
        return left
    return None


def infer_our_side_from_match_name(match_name: str | None) -> str | None:
    txt = normalize_team_name(match_name or "")
    if "נגד" not in txt:
        return None
    left, right = [normalize_team_name(x).strip() for x in txt.split("נגד", 1)]
    if is_our_team_name(left) and not is_our_team_name(right):
        return "home"
    if is_our_team_name(right) and not is_our_team_name(left):
        return "away"
    return None


def get_related_match_ids(selected_match_id: int, matches_df: pd.DataFrame) -> list[int]:
    row = matches_df[matches_df["match_id"] == selected_match_id]
    if row.empty:
        return [selected_match_id]

    match_name = row.iloc[0]["match_name"] if "match_name" in row.columns else None
    opponent = extract_opponent_from_match_name(match_name)
    if not opponent:
        return [selected_match_id]
    selected_opp_key = canonical_opponent_key(opponent)

    related = []
    for _, r in matches_df.iterrows():
        other_name = r.get("match_name")
        other_opp = extract_opponent_from_match_name(other_name)
        if other_opp and canonical_opponent_key(other_opp) == selected_opp_key:
            related.append(int(r["match_id"]))

    return sorted(set(related)) or [selected_match_id]


def format_lineup(lineup_value: str, mode: str = "numbers") -> str:
    if lineup_value is None:
        return ""
    nums = [x.strip() for x in str(lineup_value).split("-") if x and x.strip()]

    if mode == "numbers":
        return "-".join(nums)
    if mode == "names":
        return " - ".join(PLAYER_MAP.get(n, n) for n in nums)
    if mode == "both":
        return " | ".join(f"{n} {PLAYER_MAP.get(n, n)}" for n in nums)
    return str(lineup_value)
