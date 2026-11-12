"""
app.py - entry point.  Run with:  streamlit run app.py
Shows the login screen; after login shows only the pages allowed for the user's role.
"""

import os

# Limit math-library threads BEFORE numpy/torch load (avoids "OpenBLAS memory allocation failed"
# on low-memory machines).
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))

import streamlit as st

from modules.auth import ADMIN, LOCKOUT_MINUTES, AccountLocked, authenticate, log_action
from modules.database import DB_PATH, init_db

st.set_page_config(page_title="Pneumonia Detection System", page_icon="🫁", layout="centered")
init_db()


def login_page():
    st.title("🫁 Pneumonia Detection System")
    st.caption("AI-assisted chest X-ray analysis for healthcare providers.")
    with st.form("login"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Log in", type="primary")
    st.caption("Forgot password? Contact your administrator.")
    if submitted:
        try:
            user = authenticate(email, password)
        except AccountLocked as e:
            st.error(f"Too many failed attempts. This account is locked for {e.minutes_left} more "
                     f"minute(s). Please try again later or contact your administrator.")
            return
        if user:
            st.session_state["user"] = user
            st.rerun()
        else:
            st.error("Invalid credentials, or the account is deactivated.")


def logout():
    user = st.session_state.get("user")
    if user:
        log_action("LOGOUT", "User logged out", user["user_id"])
    st.session_state.clear()
    st.rerun()


user = st.session_state.get("user")

if user is None:
    st.navigation([st.Page(login_page, title="Login")], position="hidden").run()
else:
    account = st.Page("pages/account.py", title="My Account", icon="🔑")
    if user.get("must_change_password"):
        # An administrator set this password: the user must replace it before using anything else.
        pages = [account]
    else:
        dashboard = st.Page("pages/dashboard.py", title="Dashboard", icon="🏠", default=True)
        pages = [dashboard]
        if user["role"] == ADMIN:
            pages += [
                st.Page("pages/users.py", title="User Management", icon="👥"),
                st.Page("pages/logs.py", title="System Logs", icon="📜"),
            ]
        else:
            pages += [
                st.Page("pages/patient_management.py", title="Patients", icon="🧑‍⚕️"),
                st.Page("pages/upload_xray.py", title="Upload X-ray", icon="🩻"),
                st.Page("pages/history.py", title="Patient History", icon="🗂️"),
            ]
        pages.append(account)
    if not user.get("must_change_password") and st.session_state.pop("goto_dashboard", False):
        st.switch_page(dashboard)
    with st.sidebar:
        st.write(f"**{user['name']}**")
        st.caption(user["role"])
        if DB_PATH.name.startswith("demo"):
            st.warning("DEMO DATA")
        st.button("Log out", on_click=logout)
    st.navigation(pages).run()