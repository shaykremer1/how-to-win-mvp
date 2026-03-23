import os
import re
import csv
import requests
from bs4 import BeautifulSoup

MATCH_URL = "https://ibasketball.co.il/match/741657/"
HEADERS = {"User-Agent": "Mozilla/5.0"}

OUR_SIDE = "home"   # שנה ל-"away" אם צריך
START_A = [5, 1, 33, 7, 9]
START_B = [77, 3, 32, 6, 9]

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_STINTS = os.path.join(BASE_DIR, "stints_741657.csv")
OUT_PBP_DEBUG = os.path.join(BASE_DIR, "pbp_debug_741657.csv")

time_re = re.compile(r"\b(\d{1,2}):(\d{2})\b")


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


def extract_pbp_from_html():
    r = requests.get(MATCH_URL, headers=HEADERS, timeout=30)
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

        # action נמצא באח (home_event/away_event), וה-class של key-sub-* נמצא על ההורה
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

        rows.append((quarter, time, score, side, action, ev_class, raw_text))

    return rows


def save_pbp_debug(pbp_rows):
    cols = ["quarter", "time", "score", "side", "action", "ev_class", "raw_text"]
    with open(OUT_PBP_DEBUG, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for r in pbp_rows:
            w.writerow(r)
    print("Saved pbp debug:", OUT_PBP_DEBUG, "rows:", len(pbp_rows))


def build_stints(pbp_rows):
    parsed = []
    last_score_by_q = {}

    # parse
    for row in pbp_rows:
        quarter, time, score, side, action, ev_class = row[:6]
        q = quarter_num(quarter)
        t_sec = mmss_to_sec(time)
        parsed.append({
            "q": q,
            "t_sec": t_sec,
            "score": score,
            "side": side,
            "action": action,
            "ev_class": ev_class,
        })

    # sort by quarter asc, clock desc
    parsed.sort(key=lambda x: (x["q"], -x["t_sec"]))

    # fill missing score per quarter + compute diff_total
    for r in parsed:
        q = r["q"]
        if r["score"] and "-" in r["score"]:
            last_score_by_q[q] = r["score"]
        else:
            r["score"] = last_score_by_q.get(q, "")
        r["diff_total"] = score_diff(r["score"], OUR_SIDE)

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
        raise RuntimeError("לא זוהו חילופים. תבדוק ב-pbp_debug אם יש key-sub-in/out או טקסט 'שחקן נכנס/יוצא'.")

    # group subs by (q, t_sec)
    subs_by_key = {}
    for s in subs:
        subs_by_key.setdefault((s["q"], s["t_sec"]), []).append(s)

    stints = []

    A = set(START_A)
    B = set(START_B)
    prev_end_A = set(A)
    prev_end_B = set(B)

    quarters = sorted({r["q"] for r in parsed if r["q"] > 0})

    for q in quarters:
        q_rows = [r for r in parsed if r["q"] == q]
        if not q_rows:
            continue

        start_clock = max(r["t_sec"] for r in q_rows)  # usually 600
        end_clock = 0

        # carry lineup between quarters
        if q == 1:
            A = set(START_A)
            B = set(START_B)
        else:
            A = set(prev_end_A)
            B = set(prev_end_B)

        # diff_total at quarter start
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
            while len(a5) < 5: a5.append("")
            while len(b5) < 5: b5.append("")
            stints.append({
                "QUARTER": q,
                "TIME_CLOCK": sec_to_mmss(cur_clock),     # הזמן ברגע החילוף (סוף הסטינט)
                "TIME_PLAYED": sec_to_mmss(played),       # כמה זמן החמישיות שיחקו יחד
                "A1": a5[0], "A2": a5[1], "A3": a5[2], "A4": a5[3], "A5": a5[4],
                "DIFF": cur_diff_total - last_diff_total, # שינוי ההפרש בקטע
                "B1": b5[0], "B2": b5[1], "B3": b5[2], "B4": b5[3], "B5": b5[4],
            })

        # process each sub moment
        for (_, cur_clock) in q_keys:
            # diff_total at that time if exists
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

            # apply subs at this time (update A/B AFTER closing the stint)
            for s in subs_by_key[(q, cur_clock)]:
                jersey = int(s["jersey"])
                is_ours = (s["side"] == OUR_SIDE)

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

        # close last stint to end of quarter (0:00)
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


def save_stints(stints):
    cols = ["QUARTER","TIME_CLOCK","TIME_PLAYED","A1","A2","A3","A4","A5","DIFF","B1","B2","B3","B4","B5"]
    with open(OUT_STINTS, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for row in stints:
            w.writerow(row)
    print("Saved stints:", OUT_STINTS, "rows:", len(stints))


def main():
    print("SCRIPT STARTED")
    print("OUR_SIDE:", OUR_SIDE)
    print("START_A:", START_A)
    print("START_B:", START_B)

    pbp = extract_pbp_from_html()
    save_pbp_debug(pbp)

    stints = build_stints(pbp)
    save_stints(stints)

    print("DONE.")


if __name__ == "__main__":
    main()