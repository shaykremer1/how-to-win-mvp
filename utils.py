import os
import sys
import subprocess
from io import BytesIO
from datetime import date

import pandas as pd
import streamlit as st

from db import run_exec, run_query, get_conn

def ensure_matches_lookup():
    run_exec("""
    CREATE TABLE IF NOT EXISTS matches_lookup (
      match_id INT PRIMARY KEY,
      match_name TEXT NOT NULL,
      match_date DATE NULL
    );
    """)

    run_exec("""
    INSERT INTO matches_lookup (match_id, match_name, match_date)
    VALUES
      (%s, %s, %s),
      (%s, %s, %s)
    ON CONFLICT (match_id) DO UPDATE
    SET
      match_name = EXCLUDED.match_name,
      match_date = EXCLUDED.match_date;
    """, (
        741657, "עוטף דרום נגד מכבי אשדוד", "2025-11-28",
        741761, "עוטף דרום נגד הפועל אילת", "2026-02-20",
    ))

def ensure_matches_lookup_safe():
    try:
        ensure_matches_lookup()
    except Exception as e:
        st.warning(f"לא הצלחתי ליצור/לעדכן matches_lookup: {e}")

def fetch_matches_for_dropdown() -> pd.DataFrame:
    return run_query("""
        WITH ids_from_lookup AS (
            SELECT match_id, match_name, match_date
            FROM matches_lookup
        ),
        ids_from_stints AS (
            SELECT DISTINCT match_id
            FROM stints
        ),
        merged AS (
            SELECT match_id, match_name, match_date
            FROM ids_from_lookup
            UNION ALL
            SELECT s.match_id, NULL::text, NULL::date
            FROM ids_from_stints s
            WHERE NOT EXISTS (
                SELECT 1 FROM ids_from_lookup l WHERE l.match_id = s.match_id
            )
        )
        SELECT DISTINCT match_id, match_name, match_date
        FROM merged
        ORDER BY match_date DESC NULLS LAST, match_id DESC;
    """)

def get_matches_for_dropdown_safe():
    try:
        df = fetch_matches_for_dropdown()
        return df
    except Exception as e:
        return None

def make_match_label(row) -> str:
    mid = int(row["match_id"])
    name = row.get("match_name", None)
    mdate = row.get("match_date", None)

    date_part = ""
    if pd.notna(mdate):
        date_part = pd.to_datetime(mdate).strftime("%d/%m/%Y") + " | "

    if pd.isna(name) or not str(name).strip():
        return f"{date_part}Match #{mid}"
    return f"{date_part}{name} (#{mid})"

def df_to_excel_bytes(df: pd.DataFrame, sheet_name="stints") -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    return output.getvalue()

def run_ingest_match(match_id: int, our_side: str):
    script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ingest_match.py")
    if not os.path.exists(script_path):
        raise FileNotFoundError(f"לא מצאתי ingest_match.py ליד app.py. חיפשתי פה: {script_path}")

    # משתמש באותן הגדרות DB כמו db.py (דרך ENV כדי שהסקריפט שלך יקרא)
    # אם הסקריפט שלך לא משתמש ב-ENV, עדיין זה לא יפריע.
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"

    cmd = [sys.executable, script_path, str(int(match_id)), our_side]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        env=env,
        encoding="utf-8",
        errors="replace"
    )
    return result