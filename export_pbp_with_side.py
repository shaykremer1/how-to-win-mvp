import os
import re
import csv
import requests
from bs4 import BeautifulSoup

MATCH_URL = "https://ibasketball.co.il/match/741657/"
HEADERS = {"User-Agent": "Mozilla/5.0"}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_CSV = os.path.join(BASE_DIR, "pbp_with_side_741657.csv")

def clean_text(s: str) -> str:
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"^\d+\.\s*", "", s).strip()  # מוריד "77. "
    return s

def main():
    r = requests.get(MATCH_URL, headers=HEADERS, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    timeline = soup.select_one(".sp-vertical-timeline")
    if not timeline:
        raise RuntimeError("לא נמצא sp-vertical-timeline בעמוד")

    events = timeline.select(".home_event_minute, .away_event_minute")

    rows = []
    for ev in events:
        side = "home" if "home_event_minute" in (ev.get("class") or []) else "away"

        q = ev.select_one(".quarter")
        t = ev.select_one(".time")
        sc = ev.select_one(".score")
        action_el = ev.select_one(".action")
        desc_el = ev.select_one(".description")

        quarter = q.get_text(strip=True) if q else ""
        time = t.get_text(strip=True) if t else ""
        score = sc.get_text(strip=True) if sc else ""

        if action_el:
            action = clean_text(" ".join(action_el.stripped_strings))
        elif desc_el:
            action = clean_text(desc_el.get_text(" ", strip=True))
        else:
            action = clean_text(" ".join(ev.stripped_strings))

        # ניקוי: אל תחזיר רק מספרים
        if not action or re.fullmatch(r"[\d:\-– ]+", action):
            continue

        rows.append((quarter, time, score, side, action))

    with open(OUT_CSV, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["quarter", "time", "score", "side", "action"])
        w.writerows(rows)

    print("Saved:", OUT_CSV, "rows:", len(rows))

if __name__ == "__main__":
    main()