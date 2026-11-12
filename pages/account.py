import streamlit as st

from modules.auth import change_password

user = st.session_state["user"]
forced = user.get("must_change_password", False)

st.title("🔑 My Account")
st.write(f"**{user['name']}**  |  {user['email']}  |  {user['role']}")

if forced:
    st.warning("Your password was set by an administrator. Please choose a new password to continue.")

st.subheader("Change password")
with st.form("change_password", clear_on_submit=True):
    current = st.text_input("Current password", type="password")
    new = st.text_input("New password (min 8 characters)", type="password")
    confirm = st.text_input("Confirm new password", type="password")
    if st.form_submit_button("Change password", type="primary"):
        if new != confirm:
            st.error("The new passwords do not match.")
        else:
            try:
                change_password(user["user_id"], current, new)
                st.session_state["user"]["must_change_password"] = False
                if forced:
                    st.session_state["goto_dashboard"] = True   # app.py sends them to the dashboard
                    st.rerun()                                   # ...now that the full menu is unlocked
                st.success("Password changed.")
            except ValueError as e:
                st.error(str(e))