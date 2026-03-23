import streamlit as st
import pandas as pd
from datetime import date

from db import check_connection, run_exec, run_query
from utils import (
    ensure_matches_lookup_safe,
    fetch_matches_for_dropdown,
    make_match_label,
    df_to_excel_bytes,
    run_ingest_match,
)

st.set_page_config(page_title="איך לנצח — Admin", layout="centered")

ok, err = check_connection()
if not ok:
    st.error(f"DB connect failed: {err}")
    st.stop()

ensure_matches_lookup_safe()

st.title("⚙️ Admin / Data")
st.caption("כאן עושים ייבוא, ייצוא, וניהול משחקים (כדי שה-Live/Training יישארו נקיים).")

# ---------- ADD MATCH + INGEST ----------
st.subheader("➕ הוסף משחק + ייבא דאטה אוטומטי")

with st.expander("ייבוא משחק חדש (Match ID)"):
    new_match_id = st.number_input("Match ID חדש (מהאתר)", min_value=1, step=1)
    our_side = st.selectbox("עוטף דרום במשחק הזה:", ["home", "away"], index=0)

    new_match_name = st.text_input("שם המשחק (אופציונלי)", placeholder="עוטף דרום נגד ...")
    has_date = st.checkbox("יש לי תאריך משחק", value=False)
    new_match_date = st.date_input("תאריך המשחק", value=date.today(), disabled=not has_date)

    if st.button("🚀 ייבא משחק"):
        name_to_save = new_match_name.strip() if new_match_name.strip() else f"Match {int(new_match_id)}"
        date_to_save = new_match_date if has_date else None

        try:
            run_exec("""
                INSERT INTO matches_lookup (match_id, match_name, match_date)
                VALUES (%s, %s, %s)
                ON CONFLICT (match_id) DO UPDATE
                SET match_name = EXCLUDED.match_name,
                    match_date = EXCLUDED.match_date;
            """, (int(new_match_id), name_to_save, date_to_save))
        except Exception as e:
            st.error(f"שגיאה בשמירת שם/תאריך: {e}")
            st.stop()

        with st.spinner("מייבא משחק מהאתר ובונה דאטה..."):
            result = run_ingest_match(int(new_match_id), our_side)

        st.text_area("STDOUT", value=result.stdout or "", height=180)
        st.text_area("STDERR", value=result.stderr or "", height=220)

        if result.returncode != 0:
            st.error("הייבוא נכשל. תראה את ה-STDERR.")
            st.stop()

        # בדיקת counts
        stints_rows = int(run_query("SELECT COUNT(*) AS c FROM stints WHERE match_id=%s", (int(new_match_id),)).iloc[0]["c"])
        summary_rows = int(run_query("SELECT COUNT(*) AS c FROM matchup_summary WHERE match_id=%s", (int(new_match_id),)).iloc[0]["c"])
        st.success(f"✅ ייבוא הסתיים. stints: {stints_rows} | matchup_summary: {summary_rows}")
        st.rerun()

st.divider()

# ---------- Matches dropdown (Admin) ----------
st.subheader("🎚️ ניהול משחקים (לייבל/ייצוא)")

matches_df = fetch_matches_for_dropdown()
if matches_df.empty:
    st.warning("אין משחקים להצגה.")
    st.stop()

matches_df["label"] = matches_df.apply(make_match_label, axis=1)

selected_idx = st.selectbox(
    "בחר משחק",
    matches_df.index.tolist(),
    format_func=lambda i: matches_df.loc[i, "label"],
)
selected_match_id = int(matches_df.loc[selected_idx, "match_id"])
st.info(f"Match ID נבחר: {selected_match_id}")

colA, colB = st.columns(2)

with colA:
    st.subheader("🗑️ מחיקת משחק מהגלילה (רק לייבל)")
    if st.button("מחק לייבל של המשחק (matches_lookup)"):
        try:
            run_exec("DELETE FROM matches_lookup WHERE match_id = %s", (selected_match_id,))
            st.success("נמחק מ-matches_lookup ✅")
            st.rerun()
        except Exception as e:
            st.error(f"שגיאה במחיקה: {e}")

with colB:
    st.subheader("📥 ייצוא stints לאקסל")
    if st.button("ייצא stints של המשחק"):
        stints_df = run_query("""
            SELECT
                match_id, our_side, quarter, time_clock, time_played, time_played_sec,
                a1,a2,a3,a4,a5,
                diff,
                b1,b2,b3,b4,b5,
                a_lineup_key, b_lineup_key
            FROM stints
            WHERE match_id = %s
            ORDER BY quarter, time_clock DESC;
        """, params=(selected_match_id,))

        if stints_df.empty:
            st.warning("לא נמצאו stints למשחק הזה.")
        else:
            xls_bytes = df_to_excel_bytes(stints_df, sheet_name="stints")
            st.download_button(
                label="⬇ הורד קובץ Excel",
                data=xls_bytes,
                file_name=f"stints_match_{selected_match_id}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )