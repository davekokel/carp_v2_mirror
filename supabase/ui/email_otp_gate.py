from __future__ import annotations
import os, requests, streamlit as st

_SESS = "_otp_session"
_EMAIL = "_otp_email"

def _allowed(email: str) -> bool:
    allow_list = [x.strip().lower() for x in (st.secrets.get("ALLOWED_EMAILS","")).split(",") if x.strip()]
    if allow_list:
        return email.lower() in allow_list
    domain = (st.secrets.get("ALLOWED_EMAIL_DOMAIN") or "").lower().strip()
    return (not domain) or email.lower().endswith("@"+domain)

def _base():
    url = st.secrets["SUPABASE_URL"].rstrip("/")
    key = st.secrets["SUPABASE_ANON_KEY"]
    hdr = {"apikey": key, "Content-Type": "application/json"}
    return url, hdr

def _send_code(email: str):
    url, hdr = _base()
    # https://supabase.com/docs/guides/auth/auth-email#one-time-password-otp
    r = requests.post(f"{url}/auth/v1/otp", headers=hdr, json={
        "email": email,
        "create_user": True,
        "should_create_user": True,
    }, timeout=10)
    r.raise_for_status()

def _verify_code(email: str, token: str) -> str:
    url, hdr = _base()
    # https://supabase.com/docs/reference/auth/verify-otp#exchange-otp-for-a-session
    r = requests.post(f"{url}/auth/v1/token?grant_type=otp", headers=hdr, json={
        "email": email,
        "token": token,
        "type": "email",
    }, timeout=10)
    r.raise_for_status()
    data = r.json()
    return str(data.get("access_token") or "")

def require_email_otp():
    if _SESS in st.session_state:
        st.sidebar.write(f"Signed in: {st.session_state.get(_EMAIL,'')}")
        if st.sidebar.button("Sign out"):
            st.session_state.pop(_SESS, None)
            st.session_state.pop(_EMAIL, None)
            st.rerun()
        return

    st.set_page_config(page_title="🔐 Sign in", page_icon="🔐")
    st.title("🔐 Sign in")

    tab_send, tab_verify = st.tabs(["Send code", "Verify code"])

    with tab_send:
        with st.form("send"):
            email = st.text_input("Email")
            ok = st.form_submit_button("Send code")
        if ok and email:
            if not _allowed(email):
                st.error("This email is not allowed.")
                st.stop()
            try:
                _send_code(email)
                st.session_state[_EMAIL] = email
                st.success("Code sent. Check your email, then open the Verify tab.")
            except Exception as e:
                st.error("Failed to send code.")
                st.exception(e)
            st.stop()

    with tab_verify:
        email = st.session_state.get(_EMAIL, "")
        with st.form("verify"):
            token = st.text_input("6-digit code")
            ok = st.form_submit_button("Verify")
        if ok and email and token:
            try:
                access_token = _verify_code(email, token)
                if access_token:
                    st.session_state[_SESS] = access_token
                    st.session_state[_EMAIL] = email
                    st.success("Signed in")
                    st.rerun()
                else:
                    st.error("Invalid code")
                    st.stop()
            except Exception as e:
                st.error("Verification failed.")
                st.exception(e)
                st.stop()

    st.stop()