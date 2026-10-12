from datetime import date

import pandas as pd
import streamlit as st

from modules.patients import (GENDERS, age_text, get_patient, register_patient,
                              search_patients, update_patient)

user = st.session_state["user"]
st.title("🧑‍⚕️ Patients")

tab_search, tab_new = st.tabs(["🔍 Find / edit patient", "➕ Register patient"])

# ---------------- register ----------------
with tab_new:
    with st.form("register_patient", clear_on_submit=True):
        c1, c2 = st.columns(2)
        first = c1.text_input("First name")
        last = c2.text_input("Last name")
        dob = c1.date_input("Date of birth", value=None, min_value=date(1900, 1, 1),
                            max_value=date.today(), format="YYYY-MM-DD")
        gender = c2.selectbox("Gender", ["Select..."] + GENDERS)
        phone = c1.text_input("Phone")
        address = c2.text_input("Address")
        if st.form_submit_button("Register patient", type="primary"):
            try:
                _, number = register_patient(user["user_id"], first, last, dob, gender,
                                             phone or None, address or None)
                st.success(f"Patient registered. Patient number: **{number}**")
            except ValueError as e:
                st.error(str(e))

# ---------------- search / edit ----------------
with tab_search:
    q = st.text_input("Search by name, patient number or phone", placeholder="e.g. Amina or PT-00003")
    results = search_patients(q)
    if not results:
        st.info("No patients found.")
    else:
        df = pd.DataFrame(results)
        df["name"] = df["first_name"] + " " + df["last_name"]
        df["age"] = df["date_of_birth"].map(age_text)
        st.dataframe(df[["patient_number", "name", "age", "gender", "phone_no"]],
                     hide_index=True, use_container_width=True)

        st.subheader("Edit patient")
        labels = {f"{r['patient_number']} - {r['first_name']} {r['last_name']}": r["patient_id"]
                  for r in results}
        pid = labels[st.selectbox("Select patient", list(labels))]
        p = get_patient(pid)
        with st.form(f"edit_{pid}"):
            c1, c2 = st.columns(2)
            first = c1.text_input("First name", p["first_name"])
            last = c2.text_input("Last name", p["last_name"])
            dob = c1.date_input("Date of birth",
                                value=date.fromisoformat(p["date_of_birth"]) if p["date_of_birth"] else None,
                                min_value=date(1900, 1, 1), max_value=date.today(), format="YYYY-MM-DD")
            gender = c2.selectbox("Gender", GENDERS,
                                  index=GENDERS.index(p["gender"]) if p["gender"] in GENDERS else 0)
            phone = c1.text_input("Phone", p["phone_no"] or "")
            address = c2.text_input("Address", p["address"] or "")
            if st.form_submit_button("Save changes", type="primary"):
                try:
                    update_patient(pid, user["user_id"], first, last, dob, gender,
                                   phone or None, address or None)
                    st.success("Patient updated.")
                except ValueError as e:
                    st.error(str(e))