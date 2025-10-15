import os
import streamlit as st

def _off_auth():
    sb = None
    session = {"auth_mode": "off", "debug": True}
    user = {"email": "debug@local"}
    return sb, session, user

def _passcode_auth():
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
    session = {"auth_mode": "passcode"}
    user = {"email": "passcode@local"}
    return sb, session, user

def _otp_auth():
    try:
        from carp_app.ui.email_otp_gate import require_email_otp
    except Exception as e:
        st.error("OTP gate not available: " + str(e))
        st.stop()
    require_email_otp()
    sb = None
    session = {"auth_mode": "otp"}
    user = {"email": "otp@user"}
    return sb, session, user

def require_auth(*args, **kwargs):
    mode = os.getenv("AUTH_MODE", "otp").lower()
    if mode == "off":
        return _off_auth()
    if mode == "passcode":
        return _passcode_auth()
    return _otp_auth()

def require_app_unlock(*args, **kwargs):
    mode = os.getenv("AUTH_MODE", "otp").lower()
    if mode in ("off", "passcode"):
        return
    try:
        from carp_app.ui.email_otp_gate import require_email_otp
        require_email_otp()
    except Exception as e:
        st.error("Unlock failed: " + str(e))
        st.stop()
