import pandas as pd
import streamlit as st

from modules.auth import get_logs

st.title("📜 System Logs")
st.caption("Times shown in Nairobi time (EAT).")

logs = get_logs(500)
df = pd.DataFrame(logs)
if df.empty:
    st.info("No log entries yet.")
else:
    actions = ["All"] + sorted(df["action"].unique())
    pick = st.selectbox("Filter by action", actions)
    if pick != "All":
        df = df[df["action"] == pick]
    st.dataframe(df[["date_time", "user_email", "action", "description"]],
                 hide_index=True, use_container_width=True)