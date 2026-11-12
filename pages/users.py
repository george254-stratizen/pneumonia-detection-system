import sqlite3

import pandas as pd
import streamlit as st

from modules.auth import ADMIN, PROVIDER, create_user, list_users, reset_password, set_user_active
from modules.database import GENDERS

admin = st.session_state["user"]
if admin["role"] != ADMIN:
    st.error("Only administrators can manage users.")
    st.stop()

st.title("👥 User Management")

# ---- add user ----
with st.expander("➕ Add user", expanded=False):
    role = st.selectbox("Role", [PROVIDER, ADMIN], key="new_user_role")
    with st.form("add_user", clear_on_submit=True):
        c1, c2 = st.columns(2)
        first = c1.text_input("First name")
        last = c2.text_input("Last name")
        gender = c1.selectbox("Gender", ["Select..."] + GENDERS)
        phone = c2.text_input("Phone (10 digits)", max_chars=10, placeholder="0712345678")
        email = c1.text_input("Email", placeholder="name@example.com")
        password = c2.text_input("Temporary password (min 8 chars)", type="password",
                                 help="The user will be asked to choose their own password at first login.")
        department = c1.text_input("Department (optional)") if role == PROVIDER else None
        if st.form_submit_button("Create account", type="primary"):
            if gender == "Select...":
                st.error("Please select a gender.")
            else:
                try:
                    create_user(first.strip(), last.strip(), email, password, role,
                                phone_no=phone or None, gender=gender,
                                department=(department or None), must_change_password=True)
                    st.success(f"Account created for {first} {last} as {role}.")
                except sqlite3.IntegrityError:
                    st.error("That email is already registered.")
                except ValueError as e:
                    st.error(str(e))

# ---- list users ----
users = list_users()
df = pd.DataFrame(users)
df["status"] = df["is_active"].map({1: "Active", 0: "Inactive"})
df["name"] = df["first_name"] + " " + df["last_name"]
df["gender"] = df["gender"].fillna("-")
df["department"] = df["department"].fillna("-")
st.dataframe(df[["user_id", "name", "gender", "email", "role_name", "department", "status"]]
             .rename(columns={"role_name": "role"}),
             hide_index=True, width="stretch")

# ---- activate / deactivate ----
st.subheader("Activate / deactivate")
options = {f"{u['first_name']} {u['last_name']} ({u['email']}) - "
           f"{'Active' if u['is_active'] else 'Inactive'}": u for u in users}
choice = st.selectbox("Select user", list(options), key="status_user")
target = options[choice]
label = "Deactivate" if target["is_active"] else "Activate"
if st.button(f"{label} user"):
    try:
        set_user_active(target["user_id"], not target["is_active"], admin["user_id"])
        st.success(f"User {label.lower()}d.")
        st.rerun()
    except ValueError as e:
        st.error(str(e))

# ---- reset password ----
st.subheader("Reset password")
st.caption("Use this when someone forgets their password. They must choose a new one at next login.")
reset_choice = st.selectbox("Select user", list(options), key="reset_user")
if st.button("Reset password"):
    reset_target = options[reset_choice]
    try:
        temp = reset_password(reset_target["user_id"], admin["user_id"])
        st.success(f"Temporary password for {reset_target['first_name']} {reset_target['last_name']}:")
        st.code(temp, language=None)
        st.caption("Give it to the user in person or by phone. It is shown only once.")
    except ValueError as e:
        st.error(str(e))