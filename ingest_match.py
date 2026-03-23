import os
import re
import csv
import sys
import requests
from bs4 import BeautifulSoup
import sys
sys.stdout.reconfigure(encoding='utf-8')

import psycopg2
from psycopg2.extras import execute_values

# =========================
# CONFIG
# =========================
HEADERS = {"User-Agent": "Mozilla/5.0"}
time_re = re.compile(r"\b(\d{1,2}):(\d{2})\b")

# ברירת מחדל לחיבור (אפשר לדרוס עם ENV)
PGHOST = os.getenv("PGHOST", "localhost")
PGPORT = os.getenv("PGPORT", "5433")
PGDATABASE = os.getenv("PGDATABASE", "postgres")
PGUSER = os.getenv("PGUSER", "postgres")
PGPASSWORD = os.getenv("PGPASSWORD", "")  # אל תשמור בקוד

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# סטארטרים (תעדכן לפי משחק; בהמשך נעשה אוטומטי/בחירה)
START_A_DEFAULT = [5, 1, 33, 7, 9]
START_B_DEFAULT = [77, 3, 32, 6, 9]
# =========================


# ---------- helpers ----------
def build_match_url(match_id: int) -> str:
    return f"https://ibasketball.co.il/match/{match_id}/"


def clean_spaces(s: str) -> str:
    return re.sub(r"\s+", " ", str(s)).strip()


def quarter_num(q: str) -> int:
    m = re.search(r"(\d+)", str(q))
    return int(m.group(1)) if m else 0


def mmss_to_sec(s: str) -> int:
    m, ss = s.split(":")
    return int(m) * 60 + int(ss)


def sec_to_mmss(x: int) -> str:
    m = x // 60
    s = x % 60
    return f"{m:02d}:{s:02d}"


def score_diff(score: str, our_side: str):
    if not isinstance(score, str) or "-" not in score:
        return None
    a, b = score.split("-", 1)
    try:
        home = int(a.strip())
        away = int(b.strip())
    except Exception:
        return None
    return (home - away) if our_side == "home" else (away - home)


def parse_jersey(text: str):
    # תופס "32." "4." וכו'
    m = re.search(r"\b(\d{1,3})\.", str(text))
    return int(m.group(1)) if m else None


def is_sub_in(action: str) -> bool:
    a = str(action)
    return ("שחקן נכנס" in a) or (("נכנס" in a) and ("למשחק" in a or "משחק" in a))


def is_sub_out(action: str) -> bool:
    a = str(action)
    return ("שחקן יוצא" in a) or ("יוצא מהמגרש" in a) or ("יצא מהמגרש" in a) or ("יוצא" in a) or ("יצא" in a)


def sorted5(s):
    return sorted(list(s))[:5]


def lineup_key(a1, a2, a3, a4, a5):
    xs = [x for x in [a1, a2, a3, a4, a5] if x is not None]
    xs.sort()
    return "-".join(str(x) for x in xs)


# ---------- DB ----------
def get_conn():
    # מדפיס כדי שלא נשתגע איפה זה מתחבר
    print("DB CONNECT =>",
          f"host={PGHOST} port={PGPORT} db={PGDATABASE} user={PGUSER}")
    return psycopg2.connect(
        host=PGHOST,
        port=PGPORT,
        dbname=PGDATABASE,
        user=PGUSER,
        password=PGPASSWORD,
    )


def ensure_table_exists():
    ddl = """
    CREATE TABLE IF NOT EXISTS public.stints (
        id BIGSERIAL PRIMARY KEY,

        match_id BIGINT NOT NULL,
        our_side TEXT NOT NULL CHECK (our_side IN ('home','away')),

        quarter INT NOT NULL,
        time_clock TEXT NOT NULL,
        time_played TEXT NOT NULL,
        time_played_seconds INT NOT NULL,

        a1 INT NOT NULL,
        a2 INT NOT NULL,
        a3 INT NOT NULL,
        a4 INT NOT NULL,
        a5 INT NOT NULL,

        diff INT NOT NULL,

        b1 INT NOT NULL,
        b2 INT NOT NULL,
        b3 INT NOT NULL,
        b4 INT NOT NULL,
        b5 INT NOT NULL,

        a_lineup_key TEXT,
        b_lineup_key TEXT,

        created_at TIMESTAMPTZ DEFAULT NOW()
    );

    CREATE INDEX IF NOT EXISTS idx_stints_match ON public.stints(match_id);
    CREATE INDEX IF NOT EXISTS idx_stints_a_lineup ON public.stints(match_id, a_lineup_key);
    CREATE INDEX IF NOT EXISTS idx_stints_b_lineup ON public.stints(match_id, b_lineup_key);
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(ddl)
        conn.commit()
    print("Table ensured: public.stints")


# ---------- Scrape ----------
def extract_pbp(match_id: int):
    url = build_match_url(match_id)
    print("Fetching:", url)

    r = requests.get(url, headers=HEADERS, timeout=30)
    print("HTTP status:", r.status_code)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")

    timeline = soup.select_one(".sp-vertical-timeline")
    if not timeline:
        raise RuntimeError("לא נמצא sp-vertical-timeline בעמוד")

    events = timeline.select(".home_event_minute, .away_event_minute")
    print("events found:", len(events))

    rows = []
    for ev in events:
        classes = ev.get("class") or []
        side = "home" if "home_event_minute" in classes else "away"

        q_el = ev.select_one(".quarter")
        t_el = ev.select_one(".time")
        sc_el = ev.select_one(".score")

        quarter = q_el.get_text(strip=True) if q_el else ""
        time = t_el.get_text(strip=True) if t_el else ""
        score = sc_el.get_text(strip=True) if sc_el else ""

        if not time_re.search(time):
            continue

        # ev נמצא בתוך home_event_minute/away_event_minute
        # אבל הפעולה נמצאת באח parent (div של הדקה כולה)
        parent = ev.parent
        action = ""

        if parent:
            ev_block = parent.select_one(".home_event .action") if side == "home" else parent.select_one(".away_event .action")
            if ev_block:
                action = clean_spaces(ev_block.get_text(" ", strip=True))

        raw_text = clean_spaces(" ".join(parent.stripped_strings)) if parent else clean_spaces(" ".join(ev.stripped_strings))
        if not action:
            action = raw_text

        parent_cls = " ".join(parent.get("class") or []) if parent else ""
        ev_cls = " ".join(ev.get("class") or [])
        ev_class = f"{parent_cls} {ev_cls}".strip()

        rows.append((quarter, time, score, side, action, ev_class))

    print("pbp rows kept:", len(rows))
    return rows


# ---------- Build stints ----------
def build_stints(pbp_rows, our_side: str, start_a, start_b):
    parsed = []
    last_score_by_q = {}

    # parse & sort
    for quarter, time, score, side, action, ev_class in pbp_rows:
        q = quarter_num(quarter)
        t_sec = mmss_to_sec(time)
        parsed.append({
            "q": q, "t_sec": t_sec, "score": score, "side": side, "action": action, "ev_class": ev_class
        })

    parsed.sort(key=lambda x: (x["q"], -x["t_sec"]))

    # fill score + total diff
    for r in parsed:
        q = r["q"]
        if r["score"] and "-" in r["score"]:
            last_score_by_q[q] = r["score"]
        else:
            r["score"] = last_score_by_q.get(q, "")
        r["diff_total"] = score_diff(r["score"], our_side)

    # detect subs
    subs = []
    for r in parsed:
        jersey = parse_jersey(r["action"])
        if jersey is None:
            continue
        cls = r.get("ev_class", "")
        sub_in = ("key-sub-in" in cls) or is_sub_in(r["action"])
        sub_out = ("key-sub-out" in cls) or is_sub_out(r["action"])
        if sub_in or sub_out:
            subs.append({**r, "jersey": jersey, "sub_in": sub_in, "sub_out": sub_out})

    if not subs:
        raise RuntimeError("לא זוהו חילופים במשחק הזה. (subs=0)")

    subs_by_key = {}
    for s in subs:
        subs_by_key.setdefault((s["q"], s["t_sec"]), []).append(s)

    A = set(start_a)
    B = set(start_b)

    prev_end_A = set(A)
    prev_end_B = set(B)

    stints = []

    quarters = sorted({r["q"] for r in parsed if r["q"] > 0})

    for q in quarters:
        q_rows = [r for r in parsed if r["q"] == q]
        if not q_rows:
            continue

        start_clock = max(r["t_sec"] for r in q_rows)  # לרוב 600
        end_clock = 0

        # carry lineups between quarters
        if q == 1:
            A = set(start_a)
            B = set(start_b)
        else:
            A = set(prev_end_A)
            B = set(prev_end_B)

        # diff total בתחילת רבע
        last_diff_total = 0
        for r in q_rows:
            if r["t_sec"] == start_clock and r["diff_total"] is not None:
                last_diff_total = int(r["diff_total"])
                break

        q_keys = sorted([k for k in subs_by_key.keys() if k[0] == q], key=lambda x: -x[1])
        last_clock = start_clock

        def add_stint(cur_clock: int, cur_diff_total: int, played: int):
            a5 = sorted5(A)
            b5 = sorted5(B)
            while len(a5) < 5: a5.append(None)
            while len(b5) < 5: b5.append(None)

            stints.append({
                "quarter": q,
                "time_clock": sec_to_mmss(cur_clock),
                "time_played": sec_to_mmss(played),
                "time_played_seconds": played,

                "a1": a5[0], "a2": a5[1], "a3": a5[2], "a4": a5[3], "a5": a5[4],
                "diff": cur_diff_total - last_diff_total,
                "b1": b5[0], "b2": b5[1], "b3": b5[2], "b4": b5[3], "b5": b5[4],
            })

        for (_, cur_clock) in q_keys:
            # diff_total בזמן חילוף
            cur_diff_total = None
            for r in q_rows:
                if r["t_sec"] == cur_clock and r["diff_total"] is not None:
                    cur_diff_total = int(r["diff_total"])
                    break
            if cur_diff_total is None:
                cur_diff_total = last_diff_total

            played = last_clock - cur_clock
            if played > 0:
                add_stint(cur_clock, cur_diff_total, played)

            # apply subs at this clock
            for s in subs_by_key[(q, cur_clock)]:
                jersey = int(s["jersey"])
                is_ours = (s["side"] == our_side)

                if is_ours:
                    if s["sub_out"] and jersey in A:
                        A.remove(jersey)
                    if s["sub_in"] and jersey not in A:
                        A.add(jersey)
                else:
                    if s["sub_out"] and jersey in B:
                        B.remove(jersey)
                    if s["sub_in"] and jersey not in B:
                        B.add(jersey)

            last_clock = cur_clock
            last_diff_total = cur_diff_total

        # close stint until 0:00
        if last_clock > end_clock:
            end_diff_total = last_diff_total
            for r in reversed(q_rows):
                if r["diff_total"] is not None:
                    end_diff_total = int(r["diff_total"])
                    break
            played = last_clock - end_clock
            if played > 0:
                add_stint(end_clock, end_diff_total, played)

        prev_end_A = set(A)
        prev_end_B = set(B)

    return stints


# ---------- Output ----------
def save_csv(match_id: int, our_side: str, stints):
    out_csv = os.path.join(BASE_DIR, f"stints_{match_id}.csv")
    cols = [
        "match_id", "our_side",
        "quarter", "time_clock", "time_played", "time_played_seconds",
        "a1", "a2", "a3", "a4", "a5",
        "diff",
        "b1", "b2", "b3", "b4", "b5",
        "a_lineup_key", "b_lineup_key"
    ]

    with open(out_csv, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for s in stints:
            row = {
                "match_id": match_id,
                "our_side": our_side,
                **s,
                "a_lineup_key": lineup_key(s["a1"], s["a2"], s["a3"], s["a4"], s["a5"]),
                "b_lineup_key": lineup_key(s["b1"], s["b2"], s["b3"], s["b4"], s["b5"]),
            }
            w.writerow(row)

    print("Saved CSV:", out_csv, "rows:", len(stints))


def insert_to_db(match_id: int, our_side: str, stints):
    rows = []
    for s in stints:
        a_key = lineup_key(s["a1"], s["a2"], s["a3"], s["a4"], s["a5"])
        b_key = lineup_key(s["b1"], s["b2"], s["b3"], s["b4"], s["b5"])

        rows.append((
            match_id, our_side,
            s["quarter"], s["time_clock"], s["time_played"], s["time_played_seconds"],
            s["a1"], s["a2"], s["a3"], s["a4"], s["a5"],
            s["diff"],
            s["b1"], s["b2"], s["b3"], s["b4"], s["b5"],
            a_key, b_key
        ))

    sql = """
    INSERT INTO public.stints(
        match_id, our_side,
        quarter, time_clock, time_played, time_played_seconds,
        a1,a2,a3,a4,a5,
        diff,
        b1,b2,b3,b4,b5,
        a_lineup_key, b_lineup_key
    )
    VALUES %s;
    """

    with get_conn() as conn:
        with conn.cursor() as cur:
            execute_values(cur, sql, rows, page_size=1000)
        conn.commit()

    print("Inserted into DB: public.stints rows:", len(rows))


def main():
    if len(sys.argv) < 3:
        print("Usage: python ingest_match.py <match_id> <our_side: home|away>")
        sys.exit(1)

    match_id = int(sys.argv[1])
    our_side = sys.argv[2].strip().lower()
    if our_side not in ("home", "away"):
        raise ValueError("our_side must be 'home' or 'away'")

    if not PGPASSWORD:
        raise RuntimeError("PGPASSWORD חסר. תגדיר ENV לפני הרצה.")

    start_a = START_A_DEFAULT
    start_b = START_B_DEFAULT

    print("MATCH:", match_id, "OUR_SIDE:", our_side)

    pbp = extract_pbp(match_id)
    stints = build_stints(pbp, our_side, start_a, start_b)

    save_csv(match_id, our_side, stints)

    ensure_table_exists()
    insert_to_db(match_id, our_side, stints)

    print("DONE ✅")


if __name__ == "__main__":
    main()