import streamlit as st
import pandas as pd

from db import check_connection, run_query
from queries import RECO_SQL
from utils import ensure_matches_lookup_safe, fetch_matches_for_dropdown, make_match_label

st.set_page_config(page_title="איך לנצח — Live", layout="centered")

ok, err = check_connection()
if not ok:
    st.error(f"DB connect failed: {err}")
    st.stop()

ensure_matches_lookup_safe()

st.title("🎮 המלצה בזמן אמת")
st.caption("הזן 3–5 שחקנים של היריבה → קבל 3 חמישיות ירוקות + אחת אדומה.")

matches_df = fetch_matches_for_dropdown()
if matches_df.empty:
    st.warning("אין משחקים להצגה. עבור ל-Admin וייבא משחק.")
    st.stop()

matches_df["label"] = matches_df.apply(make_match_label, axis=1)

with st.sidebar:
    st.header("הגדרות")
    selected_idx = st.selectbox(
        "בחר משחק",
        matches_df.index.tolist(),
        format_func=lambda i: matches_df.loc[i, "label"],
    )
    selected_match_id = int(matches_df.loc[selected_idx, "match_id"])
    st.divider()
    min_seconds = st.slider("סף מינימום זמן (שניות)", 0, 300, 90, 15)
    min_players = st.slider("מינימום שחקנים להזנה", 1, 5, 3)

st.info(f"Match ID נבחר: {selected_match_id}")

with st.form("live_form"):
    cols = st.columns(5)
    vals = []
    for i, c in enumerate(cols, start=1):
        with c:
            vals.append(st.number_input(f"B{i}", min_value=-1, step=1, value=-1))
    submitted = st.form_submit_button("תן המלצה")

if submitted:
    b = [int(v) for v in vals if int(v) != -1]

    if len(b) < int(min_players):
        st.error(f"צריך לפחות {min_players} שחקנים (אפשר 3–5).")
        st.stop()

    if len(set(b)) != len(b):
        st.error("יש כפילויות במספרים שהזנת.")
        st.stop()

    df = run_query(
        RECO_SQL,
        params=(b, selected_match_id, selected_match_id, selected_match_id, int(min_seconds))
    )

    if df.empty:
        st.warning("אין מספיק דאטה עבור המשחק הזה (או הסף גבוה מדי).")
        st.stop()

    chosen_bkey = df["b_key"].iloc[0]
    overlap = int(df["chosen_overlap"].iloc[0])
    input_n = int(df["input_n"].iloc[0])

    if overlap < input_n:
        st.warning(f"⚠ אין התאמה מלאה. השתמשתי בחמישייה הכי דומה: `{chosen_bkey}` (חפיפה {overlap}/{input_n}).")
    else:
        st.success(f"✅ התאמה מלאה: `{chosen_bkey}`")

    show = df[["flag", "a_key", "total_seconds", "total_diff", "diff_per_min"]].copy()
    show["Minutes"] = (show["total_seconds"] / 60).round(2)
    show = show.drop(columns=["total_seconds"]).rename(columns={
        "flag": "Flag",
        "a_key": "Our Lineup",
        "total_diff": "Diff",
        "diff_per_min": "Diff / Min",
    })

    st.dataframe(show, use_container_width=True)