import streamlit as st
import pandas as pd

from db import check_connection, run_query
from queries import ALL_B_AGG_SQL, VS_B_RESPONSES_SQL, BEST_A_OVERALL_SQL
from utils import ensure_matches_lookup_safe, fetch_matches_for_dropdown, make_match_label

st.set_page_config(page_title="איך לנצח — Training", layout="centered")

# ---------- DB ----------
ok, err = check_connection()
if not ok:
    st.error(f"DB connect failed: {err}")
    st.stop()

ensure_matches_lookup_safe()

# ---------- Header ----------
st.title("🏋️ אימון — לבחור חמישייה שלהם ולראות תגובות שלנו")
st.caption("בחר חמישייה של היריבה (B) → תראה למטה אילו חמישיות שלנו (A) עבדו מולה במשחק הזה.")

# ---------- Matches dropdown ----------
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
    min_b_seconds = st.slider("סף מינימום זמן לחמישייה שלהם (שניות)", 0, 600, 120, 15)
    min_resp_seconds = st.slider("סף מינימום זמן לתגובה שלנו מול אותה חמישייה (שניות)", 0, 600, 60, 15)
    show_table = st.checkbox("הצג טבלה של כל החמישיות שלהם", value=True)

st.info(f"Match ID נבחר: {selected_match_id}")
st.markdown("---")
st.subheader("⭐ סיכום משחק: עם איזו חמישייה כדאי לשחק? (הכי טובה סה״כ)")

overall_min_seconds = st.slider("סף מינימום זמן לחמישייה שלנו (שניות)", 0, 900, 180, 30)

overall_df = run_query(
    BEST_A_OVERALL_SQL,
    params=(selected_match_id, int(overall_min_seconds), 5)
)

if overall_df.empty:
    st.warning("לא מצאתי חמישיות שלנו שעוברות את סף הזמן הזה. תוריד סף.")
else:
    show_overall = overall_df.copy()
    show_overall["Minutes"] = (show_overall["seconds_total"] / 60).round(2)
    show_overall = show_overall.drop(columns=["seconds_total"]).rename(columns={
        "a_key": "Our Lineup (A)",
        "diff_total": "Diff (Total)",
        "diff_per_min": "Diff / Min",
    })
    st.dataframe(show_overall, use_container_width=True)

    best = show_overall.iloc[0]
    st.success(
        f"🏀 ההמלצה למשחק (לפי הדאטה): **{best['Our Lineup (A)']}** "
        f"| Diff Total: **{best['Diff (Total)']:.1f}** | דקות: **{best['Minutes']:.2f}**"
    )

# ---------- 1) Load all opponent lineups ----------
b_df = run_query(ALL_B_AGG_SQL, params=(selected_match_id, int(min_b_seconds)))
if b_df.empty:
    st.warning("לא נמצאו חמישיות שלהם שעוברות את סף הזמן. תוריד סף.")
    st.stop()

# Display table (optional)
if show_table:
    b_show = b_df.copy()
    b_show["Minutes"] = (b_show["seconds_total"] / 60).round(2)
    b_show = b_show.drop(columns=["seconds_total"]).rename(columns={
        "b_key": "Their Lineup (B)",
        "diff_total": "Our Diff (Total)",
        "diff_per_min": "Our Diff / Min",
    })

    st.subheader("1) החמישיות שלהם במשחק הזה (מי פגע בנו הכי הרבה למעלה)")
    st.dataframe(b_show, use_container_width=True)

# ---------- Choose B lineup ----------
default_b = b_df.iloc[0]["b_key"]  # הראשונה בטבלה = הכי מינוס לנו (כי ממויין diff_total ASC)
chosen_b = st.selectbox(
    "בחר חמישייה שלהם (B) כדי לראות איך הגבנו מולה",
    b_df["b_key"].tolist(),
    index=0,
)

# Small summary for chosen B
chosen_row = b_df[b_df["b_key"] == chosen_b].iloc[0]
sec_total = int(chosen_row["seconds_total"])
diff_total = float(chosen_row["diff_total"])
dpm = float(chosen_row["diff_per_min"])

st.markdown("---")
st.subheader("2) הסיכום של החמישייה שבחרת")
st.write(f"**B lineup:** `{chosen_b}`")
st.write(f"**דקות:** {(sec_total/60):.2f} | **Diff מצטבר (לנו):** {diff_total:.1f} | **Diff/Min (לנו):** {dpm:.2f}")
st.caption("Diff שלילי = הם ניצחו אותנו בדקות האלה. חיובי = אנחנו ניצחנו.")

# ---------- 3) Our responses vs chosen B ----------
resp_df = run_query(VS_B_RESPONSES_SQL, params=(selected_match_id, chosen_b, int(min_resp_seconds)))
st.markdown("---")
st.subheader(f"3) כש-{chosen_b} על המגרש — אילו חמישיות שלנו (A) שיחקו מולם?")

if resp_df.empty:
    st.warning("אין מספיק דאטה של תגובות שלנו מול החמישייה הזאת לפי סף הזמן. תוריד את הסף של התגובה.")
    st.stop()

resp_show = resp_df.copy()
resp_show["Minutes"] = (resp_show["total_seconds"] / 60).round(2)
resp_show = resp_show.drop(columns=["total_seconds"]).rename(columns={
    "a_key": "Our Lineup (A)",
    "total_diff": "Diff (Total)",
    "diff_per_min": "Diff / Min",
})
st.dataframe(resp_show, use_container_width=True)

# ---------- 4) Top 3 summary ----------
best3 = resp_show.head(3)

# אם כל ה-top3 שלילי/אפס — אין לנו פתרון "מנצח", רק "הכי פחות גרוע"
if (best3["Diff / Min"] <= 0).all():
    st.warning("⚠ לפי הדאטה שיש: אין לנו תגובה חיובית מוכחת מול החמישייה הזאת. מציג את ה'פחות גרועות'.")
else:
    st.success("✅ אלו האופציות הכי טובות שלנו מול החמישייה הזאת:")

for _, row in best3.iterrows():
    st.write(
        f"- **{row['Our Lineup (A)']}** | Diff/Min: **{row['Diff / Min']:.2f}** | דקות: {row['Minutes']:.2f}"
    )