import pandas as pd
import streamlit as st

from modules.patients import get_patient, search_patients
from modules.results import patient_history
from modules.ui import render_result_detail

user = st.session_state["user"]
st.title("🗂️ Patient History")

q = st.text_input("Find patient (name, number or phone)")
patients = search_patients(q, limit=50)
if not patients:
    st.info("No matching patient.")
    st.stop()

labels = {f"{p['patient_number']} - {p['first_name']} {p['last_name']}": p["patient_id"] for p in patients}
patient = get_patient(labels[st.selectbox("Patient", list(labels))])
history = patient_history(patient["patient_id"])

if not history:
    st.info("No X-rays analysed for this patient yet.")
    st.stop()

df = pd.DataFrame(history)
df["AI"] = df["prediction"] + " (" + (df["confidence"] * 100).round(1).astype(str) + "%)"
df["Final"] = df["final_diagnosis"].fillna("Pending")
df["Match"] = df["agreed"].map({True: "Agrees", False: "Differs"}).fillna("-")
st.dataframe(df[["result_id", "date", "AI", "Final", "Match"]].rename(
    columns={"result_id": "Result", "date": "Date (EAT)"}),
    hide_index=True, use_container_width=True)

rid = st.selectbox("Open result", [h["result_id"] for h in history])
st.divider()
render_result_detail(rid, user)