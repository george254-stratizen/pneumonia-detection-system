from datetime import date, timedelta

import pandas as pd
import streamlit as st

from modules import analytics as an
from modules.auth import ADMIN
from modules.database import DB_PATH

user = st.session_state["user"]
is_admin = user["role"] == ADMIN
scope = None if is_admin else user["user_id"]      # providers only see their own work

st.title(f"Welcome, {user['name']}")
if DB_PATH.name.startswith("demo"):
    st.warning("DEMO DATA: this dashboard is showing generated sample data, not real patients.")

PERIODS = {"Last 7 days": 7, "Last 30 days": 30, "Last 90 days": 90, "All time": None}
label = st.selectbox("Period", list(PERIODS), index=1)
days = PERIODS[label]


def pct(x):
    return f"{x:.0%}"


# ---------------- headline tiles ----------------
k = an.kpi_counts(days, scope)
c1, c2, c3, c4 = st.columns(4)
if is_admin:
    accounts = an.account_status()
    c1.metric("Active users", accounts["active"])
    c1.caption(f"{accounts['inactive']} inactive")
else:
    c1.metric("Patients registered", an.patient_count(scope))
c2.metric("X-rays analysed", k["analyses"])
c3.metric("Flagged pneumonia", k["pneumonia"])
c3.caption(pct(k["pneumonia"] / k["analyses"]) + " of analyses" if k["analyses"] else " ")
c4.metric("Normal results", k["normal"])
c4.caption(pct(k["normal"] / k["analyses"]) + " of analyses" if k["analyses"] else " ")

# ---------------- cases over time ----------------
st.subheader("X-rays analysed per day")
daily = pd.DataFrame(an.analyses_per_day(days, scope))
if daily.empty:
    st.info("No X-rays analysed in this period yet.")
else:
    daily["day"] = pd.to_datetime(daily["day"])
    start = daily["day"].min() if days is None else pd.Timestamp(date.today() - timedelta(days=days - 1))
    full = pd.date_range(start, max(daily["day"].max(), pd.Timestamp(date.today())))
    daily = (daily.set_index("day").reindex(full, fill_value=0)
             .rename(columns={"pneumonia": "Pneumonia", "normal": "Normal"}))
    st.bar_chart(daily[["Pneumonia", "Normal"]], color=["#d9534f", "#4a90a4"])

# ---------------- admin only ----------------
if is_admin:
    st.subheader("Usage per provider")
    usage = pd.DataFrame(an.usage_per_provider(days))
    if usage.empty:
        st.info("No analyses in this period.")
    else:
        st.bar_chart(usage.set_index("provider")["analyses"], horizontal=True)