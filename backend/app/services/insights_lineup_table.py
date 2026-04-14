"""
Lineup-level stats: aggregate observed stints by our a_lineup_key or opponent b_lineup_key,
plus PBP-derived points and FGA when pbp_debug_{match_id}.csv exists.
"""

from __future__ import annotations

import csv
import re
from collections import defaultdict
from pathlib import Path
from typing import Literal

import pandas as pd

from backend.app.core.db import run_query
from backend.app.schemas.insights import LineupTableRowOut
from backend.app.services.common import format_lineup

REPO_ROOT = Path(__file__).resolve().parents[3]

LineupSide = Literal["our", "opponent"]


def _quarter_num(quarter: str) -> int:
    m = re.search(r"(\d+)", str(quarter))
    return int(m.group(1)) if m else 0


def _mmss_to_sec(s: str) -> int:
    parts = str(s).strip().split(":")
    if len(parts) != 2:
        return 0
    m, ss = parts
    return int(m) * 60 + int(ss)


def _parse_score(score: str | None) -> tuple[int, int] | None:
    if not score or "-" not in score:
        return None
    try:
        left, right = score.split("-", 1)
        return int(left.strip()), int(right.strip())
    except Exception:
        return None


def _fg_attempt_kind(ev_class: str) -> str | None:
    c = ev_class or ""
    if "key-threepa" in c or "key-threepm" in c:
        return "3"
    if "key-fga" in c or "key-fgm" in c:
        return "2"
    return None


def _load_pbp_rows_csv(match_id: int) -> list[dict] | None:
    path = REPO_ROOT / f"pbp_debug_{match_id}.csv"
    if not path.is_file():
        return None
    rows: list[dict] = []
    try:
        with path.open(encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for r in reader:
                q = _quarter_num(r.get("quarter", ""))
                time_txt = (r.get("time") or "").strip()
                if not time_txt or ":" not in time_txt:
                    continue
                t_sec = _mmss_to_sec(time_txt)
                rows.append(
                    {
                        "q": q,
                        "t_sec": t_sec,
                        "score": (r.get("score") or "").strip(),
                        "side": (r.get("side") or "").strip().lower(),
                        "ev_class": (r.get("ev_class") or "").strip(),
                    }
                )
    except OSError:
        return None
    rows.sort(key=lambda x: (x["q"], -x["t_sec"]))
    return rows


def _build_interval_index(
    stints_df: pd.DataFrame,
    lineup_col: str,
) -> dict[tuple[int, int], list[tuple[int, int, str]]]:
    """
    Per (match_id, quarter), list of (lo, hi, lineup_key) with membership lo < t <= hi.
    """
    out: dict[tuple[int, int], list[tuple[int, int, str]]] = defaultdict(list)
    if stints_df.empty or lineup_col not in stints_df.columns:
        return out
    for _, r in stints_df.iterrows():
        mid = int(r["match_id"])
        q = int(r["quarter"])
        key = str(r[lineup_col] or "")
        if not key:
            continue
        lo = _mmss_to_sec(str(r["time_clock"]))
        dur = int(r["time_played_seconds"] or 0)
        hi = lo + dur
        if hi <= lo:
            continue
        out[(mid, q)].append((lo, hi, key))
    for k in out:
        out[k].sort(key=lambda x: x[1])
    return out


def _find_lineup_for_clock(
    intervals_by_mq: dict[tuple[int, int], list[tuple[int, int, str]]],
    match_id: int,
    q: int,
    t_sec: int,
) -> str | None:
    brackets = intervals_by_mq.get((match_id, q))
    if not brackets:
        return None
    for lo, hi, key in brackets:
        if lo < t_sec <= hi:
            return key
    return None


def compute_lineup_table(
    match_ids: list[int],
    min_seconds: int,
    display_mode: str,
    side: LineupSide = "our",
) -> tuple[list[LineupTableRowOut], bool]:
    """
    Aggregate stints for ``match_ids`` only. ``side`` ``our`` uses a_lineup_key and diff;
    ``opponent`` uses b_lineup_key and -diff as plus/minus from that team's perspective.

    Returns rows sorted by pts_for desc when PBP exists, else by plus_minus desc.
    """
    if not match_ids:
        return [], False

    lineup_col = "a_lineup_key" if side == "our" else "b_lineup_key"

    stints_df = run_query(
        f"""
        SELECT match_id, our_side, quarter, time_clock, time_played_seconds,
               a_lineup_key, b_lineup_key, diff
        FROM stints
        WHERE match_id = ANY(%s::int[])
          AND {lineup_col} IS NOT NULL
        """,
        params=(match_ids,),
    )

    if side == "our":
        agg_sql = run_query(
            """
            SELECT
                a_lineup_key AS lineup_key,
                SUM(time_played_seconds)::bigint AS seconds_total,
                SUM(diff)::bigint AS diff_total
            FROM stints
            WHERE match_id = ANY(%s::int[])
              AND a_lineup_key IS NOT NULL
            GROUP BY a_lineup_key
            HAVING SUM(time_played_seconds) >= %s
            """,
            params=(match_ids, int(min_seconds)),
        )
    else:
        agg_sql = run_query(
            """
            SELECT
                b_lineup_key AS lineup_key,
                SUM(time_played_seconds)::bigint AS seconds_total,
                SUM(-diff)::bigint AS diff_total
            FROM stints
            WHERE match_id = ANY(%s::int[])
              AND b_lineup_key IS NOT NULL
            GROUP BY b_lineup_key
            HAVING SUM(time_played_seconds) >= %s
            """,
            params=(match_ids, int(min_seconds)),
        )

    if agg_sql.empty:
        return [], False

    our_side_map: dict[int, str] = {}
    if not stints_df.empty:
        for mid in match_ids:
            sub = stints_df[stints_df["match_id"] == mid]["our_side"].dropna().unique()
            if len(sub):
                our_side_map[int(mid)] = str(sub[0]).lower()

    intervals = _build_interval_index(stints_df, lineup_col)

    pts_for: dict[str, float] = defaultdict(float)
    pts_against: dict[str, float] = defaultdict(float)
    fg2a: dict[str, int] = defaultdict(int)
    fg3a: dict[str, int] = defaultdict(int)
    any_pbp = False

    for mid in match_ids:
        rows = _load_pbp_rows_csv(int(mid))
        if rows is None:
            continue
        any_pbp = True
        our_side = our_side_map.get(int(mid), "home")
        opp_side = "away" if our_side == "home" else "home"

        prev_parsed: tuple[int, int] | None = None
        for r in rows:
            parsed = _parse_score(r["score"])
            if parsed is None:
                continue
            away_s, home_s = parsed
            if prev_parsed is not None:
                pa, ph = prev_parsed
                da, dh = away_s - pa, home_s - ph
                if da != 0 or dh != 0:
                    lk = _find_lineup_for_clock(intervals, int(mid), int(r["q"]), int(r["t_sec"]))
                    if lk:
                        if side == "our":
                            if our_side == "home":
                                pts_for[lk] += float(dh)
                                pts_against[lk] += float(da)
                            else:
                                pts_for[lk] += float(da)
                                pts_against[lk] += float(dh)
                        else:
                            if our_side == "home":
                                pts_for[lk] += float(da)
                                pts_against[lk] += float(dh)
                            else:
                                pts_for[lk] += float(dh)
                                pts_against[lk] += float(da)
            prev_parsed = (away_s, home_s)

        shoot_side = our_side if side == "our" else opp_side
        for r in rows:
            kind = _fg_attempt_kind(r["ev_class"])
            if not kind:
                continue
            if r.get("side") != shoot_side:
                continue
            lk = _find_lineup_for_clock(intervals, int(mid), int(r["q"]), int(r["t_sec"]))
            if not lk:
                continue
            if kind == "3":
                fg3a[lk] += 1
            else:
                fg2a[lk] += 1

    rows_out: list[LineupTableRowOut] = []
    for _, r in agg_sql.iterrows():
        key = str(r["lineup_key"])
        sec = int(r["seconds_total"] or 0)
        diff_total = float(r["diff_total"] or 0)
        minutes = sec / 60.0 if sec else 0.0
        eff = (diff_total / sec) * 60.0 if sec > 0 else 0.0

        if any_pbp:
            pf = float(pts_for.get(key, 0.0))
            pa = float(pts_against.get(key, 0.0))
        else:
            # Fallback when no pbp_debug files exist for this scope:
            # keep table non-empty with a deterministic proxy derived from +/-.
            pf = float(max(diff_total, 0.0))
            pa = float(max(-diff_total, 0.0))

        rows_out.append(
            LineupTableRowOut(
                lineup_key=key,
                lineup_display=format_lineup(key, display_mode),
                player_numbers=[p for p in key.split("-") if p],
                minutes=minutes,
                pts_for=pf,
                pts_against=pa,
                fg2_attempts=int(fg2a.get(key, 0)),
                fg3_attempts=int(fg3a.get(key, 0)),
                plus_minus=diff_total,
                efficiency=float(eff),
                pbp_metrics_available=any_pbp,
            )
        )

    if any_pbp:
        rows_out.sort(key=lambda x: (-(x.pts_for or 0.0), -x.minutes, x.lineup_key))
    else:
        rows_out.sort(key=lambda x: (-x.plus_minus, -x.minutes, x.lineup_key))
    return rows_out, any_pbp


def resolve_lineup_match_scope(
    related_match_ids: list[int],
    anchor_match_id: int,
    lineup_scope: str,
    lineup_match_id: int | None,
) -> list[int]:
    """Which match_ids to use for lineup tables."""
    scope = (lineup_scope or "all").strip().lower()
    if scope != "single":
        return list(related_match_ids)
    mid = lineup_match_id if lineup_match_id is not None else anchor_match_id
    if mid in related_match_ids:
        return [int(mid)]
    if anchor_match_id in related_match_ids:
        return [int(anchor_match_id)]
    return list(related_match_ids)
