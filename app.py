"""
app.py - entry point.  Run with:  streamlit run app.py
Shows the login screen; after login shows only the pages allowed for the user's role.
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))

import streamlit as st

from modules.auth import ADMIN, authenticate, log_action
from modules.database import init_db

st.set_page_config(page_title="Pneumonia Detection System", page_icon="🫁", layout="centered")
init_db()


def login_page():
    st.title("🫁 Pneumonia Detection System")
    st.caption("AI decision support for chest X-rays. Not a substitute for clinical judgement.")
    with st.form("login"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Log in", type="primary")
    st.caption("Forgot password? Contact your administrator.")
    if submitted:
        user = authenticate(email, password)
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
    pages = [st.Page("pages/dashboard.py", title="Dashboard", icon="🏠", default=True)]
    if user["role"] == ADMIN:
        pass  # admin pages (user management, system logs) are added in a later step
    with st.sidebar:
        st.write(f"**{user['name']}**")
        st.caption(user["role"])
        st.button("Log out", on_click=logout)
    st.navigation(pages).run()