import re
import csv
import requests
from bs4 import BeautifulSoup

MATCH_URL = "https://ibasketball.co.il/match/741657/"
HEADERS = {"User-Agent": "Mozilla/5.0"}

OUT_CSV = "play_by_play_741657.csv"
OUT_XLSX = "play_by_play_741657.xlsx"


def clean_text(s: str) -> str:
    s = re.sub(r"\s+", " ", s).strip()
    # מוריד מספר חולצה בתחילת משפט כמו "77. "
    s = re.sub(r"^\d+\.\s*", "", s).strip()
    return s


def extract_pbp_rows(html: str):
    soup = BeautifulSoup(html, "html.parser")

    # קונטיינר של הפליי ביי פליי
    timeline = soup.select_one(".sp-vertical-timeline")
    if not timeline:
        # fallback כללי
        any_minute = soup.select_one(".sp-vertical-timeline-minute") or soup.select_one("[class*='vertical-timeline']")
        if any_minute:
            timeline = any_minute.parent

    if not timeline:
        raise RuntimeError("לא נמצא sp-vertical-timeline בעמוד")

    # אירועים (יכולים להגיע בכמה קלאסים שונים)
    events = timeline.select(".home_event_minute, .away_event_minute, .sp-vertical-timeline-minute")

    rows = []
    for ev in events:
        time_el = ev.select_one(".time")
        quarter_el = ev.select_one(".quarter")
        score_el = ev.select_one(".score")
        action_el = ev.select_one(".action")
        desc_el = ev.select_one(".description")

        time_txt = time_el.get_text(strip=True) if time_el else ""
        quarter_txt = quarter_el.get_text(strip=True) if quarter_el else ""
        score_txt = score_el.get_text(strip=True) if score_el else ""

        # מעדיפים action (כולל שם שחקן + תיאור)
        if action_el:
            action_txt = clean_text(" ".join(action_el.stripped_strings))
        elif desc_el:
            action_txt = clean_text(desc_el.get_text(" ", strip=True))
        else:
            # fallback: כל הטקסט באירוע, ללא זמן/רבע/סקור
            all_txt = clean_text(" ".join(ev.stripped_strings))
            for part in [quarter_txt, time_txt, score_txt]:
                if part:
                    all_txt = all_txt.replace(part, "").strip()
            action_txt = clean_text(all_txt)

        # סינון שורות “מבנה” בלי פעולה אמיתית
        if not action_txt:
            continue
        if re.fullmatch(r"[\d:\-– ]+", action_txt):
            continue

        rows.append((quarter_txt, time_txt, score_txt, action_txt))

    return rows, soup


def save_csv(rows, path: str):
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["quarter", "time", "score", "action"])
        writer.writerows(rows)


def save_excel(rows, path: str):
    # אופציונלי: רק אם מותקן pandas + openpyxl
    try:
        import pandas as pd  # type: ignore
    except Exception:
        print("⚠️ pandas לא מותקן — מדלג על Excel. (CSV כן נשמר)")
        return

    df = pd.DataFrame(rows, columns=["quarter", "time", "score", "action"])

    # פירוק score ל-home/away אם אפשר
    split = df["score"].astype(str).str.split("-", n=1, expand=True)
    if split.shape[1] == 2:
        df["score_home"] = split[0].str.strip()
        df["score_away"] = split[1].str.strip()

    try:
        df.to_excel(path, index=False)
    except Exception:
        print("⚠️ לא הצלחתי לשמור Excel. ודא ש-openpyxl מותקן: python -m pip install openpyxl")
        return


def main():
    print("SCRIPT STARTED")
    print("URL:", MATCH_URL)

    r = requests.get(MATCH_URL, headers=HEADERS, timeout=30)
    print("STATUS:", r.status_code)
    r.raise_for_status()

    rows, soup = extract_pbp_rows(r.text)

    print("PAGE TITLE:", soup.title.get_text(strip=True) if soup.title else "No title")
    print("EXTRACTED ROWS:", len(rows))

    # הדפסה קצרה לבדיקה
    print("\n---- SAMPLE (first 20) ----")
    for q, t, sc, act in rows[:20]:
        left = " ".join([p for p in [q, t] if p]).strip()
        print(f"{left} | {sc} | {act}")

    # יצוא
    save_csv(rows, OUT_CSV)
    print("\n✅ Saved CSV:", OUT_CSV)

    save_excel(rows, OUT_XLSX)
    print("✅ Saved Excel (if available):", OUT_XLSX)

    print("\nDONE.")


if __name__ == "__main__":
    main()


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_CSV = os.path.join(BASE_DIR, "play_by_play_741657.csv")

with open(OUT_CSV, "w", newline="", encoding="utf-8-sig") as f:
    writer = csv.writer(f)
    writer.writerow(["quarter", "time", "score", "action"])
    writer.writerows(rows)

print("Saved CSV to:", OUT_CSV)