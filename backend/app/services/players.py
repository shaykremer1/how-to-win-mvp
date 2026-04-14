import re

import pandas as pd
from bs4 import BeautifulSoup
from backend.app.core.ibasketball import build_match_url, extract_match_metadata, fetch_url

from backend.app.schemas.players import LeaderOut, PlayersAnalyticsOut
from backend.app.services.common import OUR_TEAM_ALIASES, PLAYER_MAP, normalize_team_name
from backend.app.services.common import get_related_match_ids
from backend.app.services.matches import fetch_matches_for_dropdown


def _clean_spaces(s) -> str:
    return re.sub(r"\s+", " ", str(s)).strip()


def _to_num_series(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce").fillna(0)


def _mmss_to_seconds(val) -> int:
    s = str(val).strip()
    if ":" not in s:
        return 0
    try:
        mm, ss = s.split(":", 1)
        return int(mm) * 60 + int(ss)
    except Exception:
        return 0


def _seconds_to_mmss(total_seconds: int) -> str:
    total_seconds = int(total_seconds)
    mm = total_seconds // 60
    ss = total_seconds % 60
    return f"{mm:02d}:{ss:02d}"


ALIASES = {
    "player": ["שחקן"],
    "jersey": ["#", "מספר", "מס'", "מס׳", "no", "number"],
    "minutes": ["דקה", "דקות", "דק"],
    "points": ["נקודות", "נק"],
    "assists": ["אסיסטים", "אס"],
    "reb_total": ["ריבאונד", "ריבאונד סהכ", "ריב סהכ", "רבי סהכ"],
    "reb_def": ["ריבאונד הגנה", "ריב הג", "רבי הג"],
    "reb_off": ["ריבאונד התקפה", "ריב הת", "רבי הת"],
    "turnovers": ["איבודים", "איב"],
    "steals": ["חטיפות", "חט"],
    "blocks": ["חסימות", "חס"],
    "fouls": ["עבירות", "עב"],
    "plus_minus": ["+/-"],
    "index": ["מדד"],
}


def _find_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    normalized = {str(col).strip(): col for col in df.columns}
    for c in candidates:
        if c in normalized:
            return normalized[c]
    for col in df.columns:
        col_name = str(col).strip()
        for c in candidates:
            if c in col_name:
                return col
    return None


def _parse_table_to_df(table) -> pd.DataFrame:
    header_row = table.select_one("thead tr")
    headers = []
    if header_row:
        headers = [_clean_spaces(th.get_text(" ", strip=True)) for th in header_row.find_all(["th", "td"])]

    rows = []
    for tr in table.select("tbody tr"):
        cells = tr.find_all(["th", "td"])
        cols = [_clean_spaces(c.get_text(" ", strip=True)) for c in cells]
        if cols:
            rows.append(cols)

    if not rows:
        return pd.DataFrame()

    max_len = max(len(r) for r in rows)
    if headers:
        if len(headers) < max_len:
            headers = headers + [f"col_{i}" for i in range(len(headers), max_len)]
        elif len(headers) > max_len:
            headers = headers[:max_len]
    else:
        headers = [f"col_{i}" for i in range(max_len)]

    return pd.DataFrame(rows, columns=headers)


def _is_our_team_title(title: str) -> bool:
    t = normalize_team_name(title).replace(".", "").replace("-", " ")
    for alias in OUR_TEAM_ALIASES:
        a = normalize_team_name(alias).replace(".", "").replace("-", " ")
        if a in t:
            return True
    return "עוטף דרום" in t


def _extract_boxscore_our_team(match_id: int) -> pd.DataFrame:
    html = fetch_url(build_match_url(match_id))
    soup = BeautifulSoup(html, "html.parser")
    blocks = soup.select("div.sp-template-event-performance")
    if not blocks:
        return pd.DataFrame()

    candidates: list[tuple[str, object]] = []
    for block in blocks:
        title_el = block.select_one("h4.sp-table-caption, h4, h3")
        title = _clean_spaces(title_el.get_text(" ", strip=True)) if title_el else ""
        table = block.select_one("table.sp-event-performance, table")
        if table:
            candidates.append((title, table))

    if not candidates:
        return pd.DataFrame()

    # 1) Prefer explicit title match to our team aliases
    for title, table in candidates:
        if _is_our_team_title(title):
            return _parse_table_to_df(table)

    # 2) Use match metadata (home/away) to identify our team title
    meta = extract_match_metadata(match_id)
    our_side = meta.get("our_side")
    target_team = None
    if our_side == "home":
        target_team = normalize_team_name(meta.get("home_team") or "")
    elif our_side == "away":
        target_team = normalize_team_name(meta.get("away_team") or "")

    if target_team:
        target_norm = target_team.replace(".", "").replace("-", " ")
        for title, table in candidates:
            title_norm = normalize_team_name(title).replace(".", "").replace("-", " ")
            if target_norm and target_norm in title_norm:
                return _parse_table_to_df(table)

    # 3) Fallback: if only one table exists, use it; otherwise use first and rely on downstream sanity checks
    return _parse_table_to_df(candidates[0][1])


def _is_time_like(s: str) -> bool:
    return bool(re.match(r"^\d{1,2}:\d{2}$", str(s).strip()))


def _text_ratio(values: pd.Series, pattern: str) -> float:
    vals = values.astype(str).head(20)
    if len(vals) == 0:
        return 0.0
    matched = sum(1 for v in vals if re.search(pattern, _clean_spaces(v)))
    return matched / max(len(vals), 1)


def _parse_player_identity(v: str) -> tuple[str, int | None]:
    txt = _clean_spaces(v)
    if not txt:
        return "-", None

    # common format from source like "9. שם שחקן"
    m = re.search(r"\b(\d{1,3})\.", txt)
    if m:
        num = int(m.group(1))
        name_part = _clean_spaces(txt.split(".", 1)[1]) if "." in txt else ""
        mapped = PLAYER_MAP.get(str(num))
        if name_part and re.search(r"[א-תA-Za-z]", name_part):
            return f"{num} - {name_part}", num
        if mapped:
            return f"{num} - {mapped}", num
        return f"{num}", num

    # jersey-only fallback
    if txt.isdigit():
        mapped = PLAYER_MAP.get(txt)
        if mapped:
            return f"{txt} - {mapped}", int(txt)
        return txt, int(txt)

    # name-only fallback
    return txt, None


def _parse_jersey_only(v) -> int | None:
    txt = _clean_spaces(v)
    if not txt:
        return None
    m = re.search(r"\b(\d{1,3})\b", txt)
    if not m:
        return None
    try:
        num = int(m.group(1))
    except Exception:
        return None
    return num if num > 0 else None


def _parse_made_attempt(v) -> tuple[float, float]:
    s = str(v).strip()
    m = re.match(r"^\s*(\d+)\s*-\s*(\d+)\s*$", s)
    if not m:
        return 0.0, 0.0
    return float(m.group(1)), float(m.group(2))


def _normalize_game_df(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()

    df = df.copy()
    df.columns = [_clean_spaces(str(c)) for c in df.columns]

    player_col = _find_col(df, ALIASES["player"]) or df.columns[0]
    jersey_col = _find_col(df, ALIASES["jersey"])
    minutes_col = _find_col(df, ALIASES["minutes"])
    points_col = _find_col(df, ALIASES["points"])
    assists_col = _find_col(df, ALIASES["assists"])
    reb_col = _find_col(df, ALIASES["reb_total"])
    plus_minus_col = _find_col(df, ALIASES["plus_minus"])
    index_col = _find_col(df, ALIASES["index"])
    reb_def_col = _find_col(df, ALIASES["reb_def"])
    reb_off_col = _find_col(df, ALIASES["reb_off"])
    tov_col = _find_col(df, ALIASES["turnovers"])
    stl_col = _find_col(df, ALIASES["steals"])
    blk_col = _find_col(df, ALIASES["blocks"])
    foul_col = _find_col(df, ALIASES["fouls"])

    # Detect known ibasketball shifted schema:
    # '#' is actually player name, 'שחקן' is actually minutes.
    shifted_schema = False
    if "#" in df.columns and "שחקן" in df.columns:
        time_ratio = _text_ratio(df["שחקן"], r"^\d{1,2}:\d{2}$")
        name_ratio = _text_ratio(df["#"], r"[א-תA-Za-z']")
        shifted_schema = time_ratio >= 0.6 and name_ratio >= 0.6

    if shifted_schema:
        player_series = df["#"]
        jersey_series = pd.Series([None] * len(df))
        minutes_series = df["שחקן"]
        points_series = df["דקה"] if "דקה" in df.columns else pd.Series([0] * len(df))
        reb_def_series = df["% קו"] if "% קו" in df.columns else pd.Series([0] * len(df))
        reb_off_series = df["ריב׳ הג׳"] if "ריב׳ הג׳" in df.columns else pd.Series([0] * len(df))
        reb_total_series = df["ריב׳ הת׳"] if "ריב׳ הת׳" in df.columns else pd.Series([0] * len(df))
        assists_series = df["איב'"] if "איב'" in df.columns else pd.Series([0] * len(df))
        turnovers_series = df["חט'"] if "חט'" in df.columns else pd.Series([0] * len(df))
        steals_series = df["עב' על"] if "עב' על" in df.columns else pd.Series([0] * len(df))
        blocks_series = df["אס'"] if "אס'" in df.columns else pd.Series([0] * len(df))
        fouls_series = df["ריב' סהכ"] if "ריב' סהכ" in df.columns else pd.Series([0] * len(df))
        index_series = df["חס' על"] if "חס' על" in df.columns else pd.Series([0] * len(df))
        plus_minus_series = df["מדד"] if "מדד" in df.columns else pd.Series([0] * len(df))
    else:
        player_series = df[player_col]
        jersey_series = df[jersey_col] if jersey_col else pd.Series([None] * len(df))
        minutes_series = df[minutes_col] if minutes_col else pd.Series([0] * len(df))
        points_series = df[points_col] if points_col else pd.Series([0] * len(df))
        reb_def_series = df[reb_def_col] if reb_def_col else pd.Series([0] * len(df))
        reb_off_series = df[reb_off_col] if reb_off_col else pd.Series([0] * len(df))
        reb_total_series = df[reb_col] if reb_col else pd.Series([0] * len(df))
        assists_series = df[assists_col] if assists_col else pd.Series([0] * len(df))
        turnovers_series = df[tov_col] if tov_col else pd.Series([0] * len(df))
        steals_series = df[stl_col] if stl_col else pd.Series([0] * len(df))
        blocks_series = df[blk_col] if blk_col else pd.Series([0] * len(df))
        fouls_series = df[foul_col] if foul_col else pd.Series([0] * len(df))
        index_series = df[index_col] if index_col else pd.Series([0] * len(df))
        plus_minus_series = df[plus_minus_col] if plus_minus_col else pd.Series([0] * len(df))

    out = pd.DataFrame()
    parsed = player_series.astype(str).apply(_parse_player_identity)
    out["שחקן"] = parsed.apply(lambda x: x[0])
    out["מספר"] = parsed.apply(lambda x: x[1])
    fallback_jersey = jersey_series.apply(_parse_jersey_only)
    out["מספר"] = out["מספר"].where(out["מספר"].notna(), fallback_jersey)
    out["מספר"] = pd.to_numeric(out["מספר"], errors="coerce")
    out["מספר"] = out["מספר"].where(out["מספר"] > 0)
    out["שחקן"] = out.apply(
        lambda r: (
            str(r["שחקן"])
            if re.match(r"^\d+\s*-\s*.+", str(r["שחקן"]))
            else (f"{int(r['מספר'])} - {str(r['שחקן'])}" if pd.notna(r["מספר"]) and str(r["שחקן"]).strip() not in {"", "-", "nan"} else str(r["שחקן"]))
        ),
        axis=1,
    )
    out["_seconds"] = minutes_series.apply(_mmss_to_seconds)
    out["דקות"] = out["_seconds"].apply(_seconds_to_mmss)
    out["נקודות"] = _to_num_series(points_series)
    out["ריבאונד"] = _to_num_series(reb_total_series)
    out["ריבאונד הגנה"] = _to_num_series(reb_def_series)
    out["ריבאונד התקפה"] = _to_num_series(reb_off_series)
    out["אסיסטים"] = _to_num_series(assists_series)
    out["איבודים"] = _to_num_series(turnovers_series)
    out["חטיפות"] = _to_num_series(steals_series)
    out["חסימות"] = _to_num_series(blocks_series)
    out["עבירות"] = _to_num_series(fouls_series)
    out["+/-"] = _to_num_series(plus_minus_series)
    out["מדד"] = _to_num_series(index_series)

    # if total rebounds missing but split exists
    if out["ריבאונד"].sum() == 0 and (out["ריבאונד הגנה"].sum() > 0 or out["ריבאונד התקפה"].sum() > 0):
        out["ריבאונד"] = out["ריבאונד הגנה"] + out["ריבאונד התקפה"]

    # derived (interpretable)
    out["יעילות"] = (
        out["נקודות"]
        + out["ריבאונד"]
        + out["אסיסטים"]
        + out["חטיפות"]
        + out["חסימות"]
        - out["איבודים"]
    )
    out["נקודות לדקה"] = (out["נקודות"] / (out["_seconds"].where(out["_seconds"] > 0, 1) / 60.0)).fillna(0).round(2)
    out["מדד לדקה"] = (out["מדד"] / (out["_seconds"].where(out["_seconds"] > 0, 1) / 60.0)).fillna(0).round(2)
    out["השפעה לדקה"] = (out["+/-"] / (out["_seconds"].where(out["_seconds"] > 0, 1) / 60.0)).fillna(0).round(2)
    out = out[
        ~out["שחקן"].astype(str).str.contains(r"^-$|^nan$", case=False, regex=True)
    ].copy()
    # remove obvious non-player summary rows
    out = out[
        ~out["שחקן"].astype(str).str.contains(r"TOTAL|סה\"כ|סך הכל", case=False, regex=True)
    ].copy()
    return out.reset_index(drop=True)


def _get_leaders(df: pd.DataFrame) -> list[LeaderOut]:
    if df.empty or "שחקן" not in df.columns:
        return []

    stats = ["נקודות", "ריבאונד", "אסיסטים", "מדד", "+/-", "יעילות", "נקודות לדקה", "מדד לדקה", "השפעה לדקה"]
    leaders: list[LeaderOut] = []
    for stat in stats:
        if stat not in df.columns:
            continue
        temp = df.copy()
        temp[stat] = pd.to_numeric(temp[stat], errors="coerce")
        temp = temp.dropna(subset=[stat])
        if temp.empty or float(temp[stat].max()) == 0.0:
            continue
        row = temp.loc[temp[stat].idxmax()]
        leaders.append(LeaderOut(stat=stat, player=str(row["שחקן"]), value=float(row[stat])))
    return leaders


def _fetch_single(match_id: int) -> pd.DataFrame:
    raw = _extract_boxscore_our_team(match_id)
    return _normalize_game_df(raw)


def get_players_analytics(mode: str, match_id: int | None = None) -> PlayersAnalyticsOut:
    mode = (mode or "single").lower()
    if mode == "aggregate":
        mode = "seasonal_aggregate"
    if mode not in {"single", "opponent_aggregate", "seasonal_aggregate", "average"}:
        mode = "single"

    if mode == "single":
        if not match_id:
            return PlayersAnalyticsOut(
                mode=mode,
                match_ids=[],
                columns=[],
                rows=[],
                leaders=[],
                calculation_note="Single match mode requires a match_id.",
            )
        df = _fetch_single(match_id)
        leaders = _get_leaders(df)
        display_cols = [
            "שחקן",
            "מספר",
            "דקות",
            "נקודות",
            "ריבאונד",
            "אסיסטים",
            "איבודים",
            "חטיפות",
            "חסימות",
            "מדד",
            "יעילות",
            "+/-",
            "נקודות לדקה",
            "מדד לדקה",
            "השפעה לדקה",
        ]
        display = df[[c for c in display_cols if c in df.columns]].sort_values("נקודות", ascending=False, kind="stable")
        return PlayersAnalyticsOut(
            mode=mode,
            match_ids=[match_id],
            columns=list(display.columns),
            rows=display.fillna("").to_dict(orient="records"),
            leaders=leaders,
            calculation_note="Single match: values are taken from one selected game.",
        )

    matches_df = fetch_matches_for_dropdown()
    if mode == "opponent_aggregate":
        if not match_id:
            return PlayersAnalyticsOut(
                mode=mode,
                match_ids=[],
                columns=[],
                rows=[],
                leaders=[],
                calculation_note="Opponent aggregate mode requires a match_id (used as opponent context).",
            )
        match_ids = get_related_match_ids(int(match_id), matches_df)
    else:
        match_ids = [int(x) for x in matches_df["match_id"].tolist()] if not matches_df.empty else []
    frames = []
    for mid in match_ids:
        try:
            one = _fetch_single(mid)
            if not one.empty:
                one["games"] = (one["_seconds"] > 0).astype(int)
                frames.append(one)
        except Exception:
            continue

    if not frames:
        return PlayersAnalyticsOut(
            mode=mode,
            match_ids=match_ids,
            columns=[],
            rows=[],
            leaders=[],
            calculation_note="No parsable boxscore data found across selected matches.",
        )

    big = pd.concat(frames, ignore_index=True).drop(
        columns=["נקודות לדקה", "מדד לדקה", "השפעה לדקה"],
        errors="ignore",
    )
    big["מספר"] = pd.to_numeric(big["מספר"], errors="coerce").fillna(-1).astype(int)
    agg = big.groupby(["שחקן", "מספר"], as_index=False).sum(numeric_only=True)

    # Recompute per-minute metrics from aggregated base values (not from per-game sums)
    minute_base_agg = (agg["_seconds"].where(agg["_seconds"] > 0, 1) / 60.0)
    agg["נקודות לדקה"] = (agg["נקודות"] / minute_base_agg).fillna(0).round(2)
    agg["מדד לדקה"] = (agg["מדד"] / minute_base_agg).fillna(0).round(2)
    agg["השפעה לדקה"] = (agg["+/-"] / minute_base_agg).fillna(0).round(2)

    if mode == "average":
        games = agg["games"].replace(0, 1)
        for col in [
            "_seconds",
            "נקודות",
            "ריבאונד",
            "אסיסטים",
            "איבודים",
            "חטיפות",
            "חסימות",
            "מדד",
            "יעילות",
            "+/-",
        ]:
            if col in agg.columns:
                agg[col] = (agg[col] / games).round(2)
        # per-minute metrics should be based on averaged per-game values and averaged minutes
        minute_base = (agg["_seconds"].where(agg["_seconds"] > 0, 1) / 60.0)
        agg["נקודות לדקה"] = (agg["נקודות"] / minute_base).fillna(0).round(2)
        agg["מדד לדקה"] = (agg["מדד"] / minute_base).fillna(0).round(2)
        agg["השפעה לדקה"] = (agg["+/-"] / minute_base).fillna(0).round(2)

    agg["דקות"] = agg["_seconds"].apply(lambda x: _seconds_to_mmss(int(round(x))))
    display_cols = [
        "שחקן",
        "מספר",
        "games",
        "דקות",
        "נקודות",
        "ריבאונד",
        "אסיסטים",
        "איבודים",
        "חטיפות",
        "חסימות",
        "מדד",
        "יעילות",
        "+/-",
        "נקודות לדקה",
        "מדד לדקה",
        "השפעה לדקה",
    ]
    display = agg[[c for c in display_cols if c in agg.columns]].copy()
    if "מספר" in display.columns:
        display["מספר"] = display["מספר"].replace(-1, "")
    if "games" in display.columns:
        display = display.rename(columns={"games": "משחקים"})
    if mode == "average":
        display = display.rename(
            columns={
                "דקות": "דקות ממוצע למשחק",
                "נקודות": "נקודות למשחק",
                "ריבאונד": "ריבאונד למשחק",
                "אסיסטים": "אסיסטים למשחק",
                "איבודים": "איבודים למשחק",
                "חטיפות": "חטיפות למשחק",
                "חסימות": "חסימות למשחק",
                "מדד": "מדד למשחק",
                "יעילות": "יעילות למשחק",
                "+/-": "+/- למשחק",
            }
        )
    sort_col = "נקודות למשחק" if mode == "average" else "נקודות"
    if sort_col in display.columns:
        display = display.sort_values(sort_col, ascending=False, kind="stable")

    leaders_source = display.rename(
        columns={
            "משחקים": "games",
            "נקודות למשחק": "נקודות",
            "ריבאונד למשחק": "ריבאונד",
            "אסיסטים למשחק": "אסיסטים",
            "מדד למשחק": "מדד",
            "+/- למשחק": "+/-",
            "יעילות למשחק": "יעילות",
        }
    )
    leaders = _get_leaders(leaders_source)
    return PlayersAnalyticsOut(
        mode=mode,
        match_ids=match_ids,
        columns=list(display.columns),
        rows=display.fillna("").to_dict(orient="records"),
        leaders=leaders,
        calculation_note=(
            "Aggregate vs opponent: totals across meetings vs selected opponent."
            if mode == "opponent_aggregate"
            else (
                "Seasonal aggregate: totals across all parsed matches."
                if mode == "seasonal_aggregate"
                else "Average mode: per-game averages across games where player logged minutes."
            )
        ),
    )


def get_single_game_players(match_id: int) -> list[dict]:
    df = _extract_boxscore_our_team(match_id)
    df = df.fillna("")
    return df.to_dict(orient="records")


def get_single_game_columns(match_id: int) -> list[str]:
    df = _extract_boxscore_our_team(match_id)
    return [str(c) for c in df.columns]
