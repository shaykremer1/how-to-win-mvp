import streamlit as st
from db import check_connection
from utils import ensure_matches_lookup_safe, get_matches_for_dropdown_safe

st.set_page_config(page_title="איך לנצח - MVP", layout="centered")

st.title("איך לנצח — MVP")
st.caption("בחר עמוד מהתפריט בצד שמאל 👈 (Live / Training / Admin)")

ok, err = check_connection()
if not ok:
    st.error(f"DB connect failed: {err}")
    st.stop()

ensure_matches_lookup_safe()

matches_df = get_matches_for_dropdown_safe()
if matches_df is None:
    st.warning("לא הצלחתי להביא משחקים מה-DB.")
elif matches_df.empty:
    st.info("אין משחקים עדיין. לך ל-Admin → ייבוא משחק.")
else:
    st.success(f"✅ מחובר ל-DB. נמצאו {len(matches_df)} משחקים.")
    st.write("ל־Live: המלצה בזמן אמת לפי חמישייה שלהם.")
    st.write("ל־Training: אימון מול החמישייה הכי חזקה שלהם.")
    st.write("ל־Admin: ייבוא/ייצוא/ניהול משחקים.")