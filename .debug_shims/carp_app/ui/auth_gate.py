import os, streamlit as st
def require_auth(*args, **kwargs):
    expected = os.getenv("PASSCODE", "letmein")
    st.sidebar.markdown("### auth login")
    code = st.sidebar.text_input("Enter passcode", type="password")
    ok = st.sidebar.button("Unlock")
    if "auth_ok" not in st.session_state:
        st.session_state.auth_ok = False
    if ok and code == expected:
        st.session_state.auth_ok = True
    if not st.session_state.auth_ok:
        st.stop()
    sb = None
    session = {"debug": True}
    user = {"email": "passcode@local"}
    return sb, session, user
def require_app_unlock(*args, **kwargs):
    return
