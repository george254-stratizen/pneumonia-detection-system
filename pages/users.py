import sqlite3

import pandas as pd
import streamlit as st

from modules.auth import PROVIDER, create_user, list_users, set_user_active

admin = st.session_state["user"]
st.title("👥 User Management")

# ---- add provider ----
with st.expander("➕ Add healthcare provider", expanded=False):
    with st.form("add_provider", clear_on_submit=True):
        c1, c2 = st.columns(2)
        first = c1.text_input("First name")
        last = c2.text_input("Last name")
        email = c1.text_input("Email")
        phone = c2.text_input("Phone")
        license_no = c1.text_input("License number")
        profession = c2.text_input("Profession (e.g. Clinician, Radiographer)")
        department = c1.text_input("Department")
        password = c2.text_input("Temporary password (min 8 chars)", type="password")
        if st.form_submit_button("Create account", type="primary"):
            if not (first and last and email and password):
                st.error("First name, last name, email and password are required.")
            else:
                try:
                    create_user(first, last, email, password, PROVIDER, phone_no=phone,
                                license_number=license_no, profession=profession,
                                department=department)
                    st.success(f"Account created for {first} {last}.")
                except sqlite3.IntegrityError:
                    st.error("That email is already registered.")
                except ValueError as e:
                    st.error(str(e))

# ---- list users ----
users = list_users()
df = pd.DataFrame(users)
df["status"] = df["is_active"].map({1: "Active", 0: "Inactive"})
df["name"] = df["first_name"] + " " + df["last_name"]
st.dataframe(df[["user_id", "name", "email", "role_name", "department", "status"]],
             hide_index=True, use_container_width=True)

# ---- activate / deactivate ----
st.subheader("Activate / deactivate")
options = {f"{u['first_name']} {u['last_name']} ({u['email']}) - "
           f"{'Active' if u['is_active'] else 'Inactive'}": u for u in users}
choice = st.selectbox("Select user", list(options))
target = options[choice]
label = "Deactivate" if target["is_active"] else "Activate"
if st.button(f"{label} user"):
    try:
        set_user_active(target["user_id"], not target["is_active"], admin["user_id"])
        st.success(f"User {label.lower()}d.")
        st.rerun()
    except ValueError as e:
        st.error(str(e))