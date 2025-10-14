from __future__ import annotations
import os, sys, hashlib
from pathlib import Path
import streamlit as st

def require_app_unlock():
    locked = bool(st.secrets.get("APP_LOCKED", False))
    if not locked:
        return
    ok = st.session_state.get("_app_unlocked", False)
    if ok:
        return
    st.title("🔒 Carp")
    st.caption("This app is locked. Enter the passphrase to continue.")
    pw = st.text_input("Passphrase", type="password")
    submit = st.button("Unlock", type="primary")
    if submit:
        sha_expected = (st.secrets.get("APP_PASSWORD_SHA256") or "").strip().lower()
        sha_entered = hashlib.sha256((pw or "").encode("utf-8")).hexdigest()
        if sha_entered == sha_expected:
            st.session_state["_app_unlocked"] = True
            st.rerun()
        else:
            st.error("Incorrect passphrase.")
    st.stop()

ROOT = Path(__file__).resolve().parents[2]
LOCAL_SUPABASE = Path(__file__).resolve().parents[1]
for p in (str(LOCAL_SUPABASE), str(ROOT)):
    while p in sys.path:
        try:
            sys.path.remove(p)
        except ValueError:
            break
if "supabase" in sys.modules:
    del sys.modules["supabase"]
from supabase import create_client
sys.path.insert(0, str(ROOT))

_SUPABASE_URL = os.getenv("SUPABASE_URL", "")
_SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")

@st.cache_resource(show_spinner=False)
def _client():
    if not _SUPABASE_URL or not _SUPABASE_ANON_KEY:
        raise RuntimeError("SUPABASE_URL / SUPABASE_ANON_KEY not set")
    return create_client(_SUPABASE_URL, _SUPABASE_ANON_KEY)

def _restore_session_if_needed(sb):
    toks = st.session_state.get("sb_tokens") or {}
    at, rt = toks.get("access"), toks.get("refresh")
    if at and rt:
        try:
            try:
                sb.auth.set_session(at, rt)
            except TypeError:
                sb.auth.set_session({"access_token": at, "refresh_token": rt})
        except Exception:
            pass

def require_login():
    sb = _client()

    # DEV BYPASS (local-only): set AUTH_DEV_BYPASS=1 to skip OTP while testing
    if os.getenv("AUTH_DEV_BYPASS") == "1":
        fake_user = type("User", (), {"email": "dev@local"})()
        return sb, None, fake_user

    _restore_session_if_needed(sb)
    session = sb.auth.get_session()
    user = getattr(session, "user", None) if session else None
    if not user:
        try: st.query_params.clear()
        except Exception: pass
        st.switch_page("pages/010_auth_login.py")
        st.stop()
    return sb, session, user

def require_auth():
    require_app_unlock()
    return require_login()