import hashlib
import os
import streamlit as st
from typing import Optional, Dict, Any

SESSION_KEY = "app_auth_ok"

def _sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def _allowed_hash_from_secrets() -> Optional[str]:
    """Return the allowed SHA-256 hash from secrets (APP_PASSWORD or APP_PASSWORD_SHA256)."""
    pw_plain = st.secrets.get("APP_PASSWORD")
    pw_hash  = st.secrets.get("APP_PASSWORD_SHA256")
    if pw_hash:
        return str(pw_hash).strip().lower()
    if pw_plain:
        return _sha256(str(pw_plain))
    return None

def require_app_access(title: Optional[str] = "🔐 Private app") -> None:
    """Gate the whole app/page behind a shared password."""
    if st.session_state.get(SESSION_KEY):
        return
    allowed_hash = _allowed_hash_from_secrets()
    if not allowed_hash:
        st.error("App is locked but no APP_PASSWORD/APP_PASSWORD_SHA256 is set in Secrets.")
        st.stop()

    st.title(title or "🔐 Private app")
    with st.form("app_login", clear_on_submit=False):
        pw = st.text_input("App password", type="password")
        ok = st.form_submit_button("Enter")

    if ok:
        if _sha256(pw or "") == allowed_hash:
            st.session_state[SESSION_KEY] = True
            st.rerun()
        else:
            st.error("Incorrect password.")
            st.stop()
    else:
        st.stop()

# ---------------- Read-only helpers ----------------

def _truthy(v: object) -> bool:
    if isinstance(v, str):
        return v.strip().lower() in {"1", "true", "yes", "on"}
    return bool(v)

def is_read_only() -> bool:
    # Prefer Secrets; fall back to env
    if "READ_ONLY" in st.secrets:
        return _truthy(st.secrets.get("READ_ONLY"))
    return _truthy(os.getenv("READ_ONLY", ""))

def read_only_banner() -> None:
    if is_read_only():
        st.info("🔒 Read-only mode is ON — write actions are disabled.", icon="🔒")

def guard_writes() -> bool:
    """
    Simple guard used by pages like:
        if not guard_writes():
            st.stop()
    Returns True if writes are allowed; False if blocked by read-only mode.
    """
    if is_read_only():
        st.warning("Read-only mode is ON; write actions are disabled.")
        return False
    return True

def button_guard(label: str = "Submit") -> Dict[str, Any]:
    """
    Optional helper for st.button:
        st.button("Do it", **button_guard())
    Returns kwargs like {"disabled": True, "help": "..."} when read-only.
    """
    if is_read_only():
        return {"disabled": True, "help": "Disabled in read-only mode"}
    return {}