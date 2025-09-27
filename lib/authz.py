import hashlib
import streamlit as st
SESSION_KEY = "app_auth_ok"
def _sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()
def _allowed_hash_from_secrets() -> str | None:
    pw_plain = st.secrets.get("APP_PASSWORD")
    pw_hash  = st.secrets.get("APP_PASSWORD_SHA256")
    if pw_hash:
        return str(pw_hash).strip().lower()
    if pw_plain:
        return _sha256(str(pw_plain))
    return None
def require_app_access(title: str = "🔐 Private app"):
    if st.session_state.get(SESSION_KEY):
        return
    allowed_hash = _allowed_hash_from_secrets()
    if not allowed_hash:
        st.error("APP is locked but no APP_PASSWORD/APP_PASSWORD_SHA256 is set in Secrets.")
        st.stop()
    st.title(title)
    with st.form("app_login", clear_on_submit=False):
        pw = st.text_input("App password", type="password")
        ok = st.form_submit_button("Enter")
    if ok:
        if _sha256(pw) == allowed_hash:
            st.session_state[SESSION_KEY] = True
            st.rerun()
        else:
            st.error("Incorrect password.")
            st.stop()
    else:
        st.stop()

import streamlit as st

def is_read_only() -> bool:
    # Streamlit secrets set as strings; accept bool-ish values
    val = st.secrets.get("READ_ONLY", False)
    if isinstance(val, str):
        return val.strip().lower() in {"1","true","yes","on"}
    return bool(val)

def read_only_banner():
    if is_read_only():
        st.info("🔒 Read-only mode is ON — write actions are disabled.", icon="🔒")

def guard_writes(enabled: bool, label: str = "Submit"):
    """
    Return (disabled_flag, help_text) pair you can pass to st.button()
    """
    if is_read_only():
        return True, "Disabled in read-only mode"
    if not enabled:
        return True, f"Disabled: {label} not available"
    return False, None
