from __future__ import annotations
import streamlit as st
from supabase import create_client, Client

_SESS = "_otp_session"
_EMAIL = "_otp_email"

def _allowed(email: str) -> bool:
    allow_list = [x.strip().lower() for x in (st.secrets.get("ALLOWED_EMAILS","")).split(",") if x.strip()]
    if allow_list:
        return email.lower() in allow_list
    domain = (st.secrets.get("ALLOWED_EMAIL_DOMAIN") or "").lower().strip()
    return (not domain) or email.lower().endswith("@"+domain)

def _client() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_ANON_KEY"]
    return create_client(url, key)

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
            _client().auth.sign_in_with_otp({"email": email})
            st.session_state[_EMAIL] = email
            st.success("Code sent. Check your email, then open the Verify tab.")
            st.stop()

    with tab_verify:
        email = st.session_state.get(_EMAIL, "")
        with st.form("verify"):
            token = st.text_input("6-digit code")
            ok = st.form_submit_button("Verify")
        if ok and email and token:
            r = _client().auth.verify_otp({"email": email, "token": token, "type": "email"})
            if r and r.session and r.session.access_token:
                st.session_state[_SESS] = r.session.access_token
                st.session_state[_EMAIL] = email
                st.success("Signed in")
                st.rerun()
            else:
                st.error("Invalid code")
                st.stop()

    st.stop()