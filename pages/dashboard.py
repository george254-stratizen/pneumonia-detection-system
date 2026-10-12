import streamlit as st

user = st.session_state["user"]
st.title(f"Welcome, {user['name']}")
st.write(f"Signed in as **{user['role']}**.")
st.info("Patient management, X-ray upload and results are coming in the next steps.")