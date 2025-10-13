# supabase/ui/email_otp_gate.py
from __future__ import annotations
import os
import requests
import streamlit as st

_SESS = "_otp_session"     # access_token
_EMAIL = "_otp_email"
_RTOK = "_otp_refresh"     # refresh_token

def require_email_otp():
    mode = str(
        st.secrets.get("AUTH_MODE")
        or os.getenv("AUTH_MODE")
        or "otp"
    ).strip().lower()

    # temporary debug so you can see which mode is active
    st.sidebar.caption(f"auth mode: {mode}")

    if mode == "off":
        return
    if mode == "unlock":
        from supabase.ui.auth_gate import require_app_unlock
        require_app_unlock()
        return

def _base():
    url = st.secrets["SUPABASE_URL"].rstrip("/")
    key = st.secrets["SUPABASE_ANON_KEY"]
    hdr = {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    return url, hdr

def _send_code(email: str):
    url, hdr = _base()
    r = requests.post(f"{url}/auth/v1/otp", headers=hdr, json={
        "email": email, "type": "email", "create_user": True, "should_create_user": True
    }, timeout=15)
    if r.status_code >= 400:
        raise RuntimeError(f"/otp {r.status_code}: {r.text}")

def _verify_code(email: str, token: str):
    url, hdr = _base()
    r = requests.post(f"{url}/auth/v1/token?grant_type=otp", headers=hdr, json={
        "email": email, "token": token, "type": "email"
    }, timeout=15)
    if r.status_code >= 400:
        raise RuntimeError(f"/token {r.status_code}: {r.text}")
    data = r.json() or {}
    return data.get("access_token") or "", data.get("refresh_token") or "", (data.get("user") or {}).get("email") or email

def _refresh_with_token(refresh_token: str):
    url, hdr = _base()
    r = requests.post(f"{url}/auth/v1/token?grant_type=refresh_token", headers=hdr, json={
        "refresh_token": refresh_token
    }, timeout=15)
    if r.status_code >= 400:
        return "", ""
    data = r.json() or {}
    return data.get("access_token") or "", data.get("refresh_token") or ""

def require_email_otp():
    mode = str(
        st.secrets.get("AUTH_MODE")
        or os.getenv("AUTH_MODE")
        or "otp"
    ).strip().lower()

    # show what mode the gate thinks it's in (temporary debug)
    st.sidebar.caption(f"auth mode: {mode}")

    if mode == "off":
        return
    if mode == "unlock":
        from supabase.ui.auth_gate import require_app_unlock
        require_app_unlock()
        return
    # ----------------------------------------------------------------

    # 🔄 Silent sign-in using stored refresh token
    if _SESS not in st.session_state and st.session_state.get(_RTOK):
        at, rt = _refresh_with_token(st.session_state[_RTOK])
        if at:
            st.session_state[_SESS] = at
            if rt: st.session_state[_RTOK] = rt

    # Already signed in?
    if _SESS in st.session_state:
        st.sidebar.write(f"Signed in: {st.session_state.get(_EMAIL,'')}")
        if st.sidebar.button("Sign out"):
            for k in (_SESS, _EMAIL, _RTOK): st.session_state.pop(k, None)
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
                st.error("This email is not allowed."); st.stop()
            try:
                _send_code(email)
                st.session_state[_EMAIL] = email
                st.success("Code sent. Check your email, then open the Verify tab.")
            except Exception as e:
                st.error("Failed to send code."); st.exception(e)
            st.stop()

    with tab_verify:
        email = st.session_state.get(_EMAIL, "")
        with st.form("verify"):
            token = st.text_input("6-digit code")
            ok = st.form_submit_button("Verify")
        if ok and email and token:
            try:
                at, rt, em = _verify_code(email, token)
                if at:
                    st.session_state[_SESS] = at
                    st.session_state[_EMAIL] = em
                    if rt: st.session_state[_RTOK] = rt
                    st.success("Signed in"); st.rerun()
                else:
                    st.error("Invalid code"); st.stop()
            except Exception as e:
                st.error("Verification failed."); st.exception(e); st.stop()
    st.stop()