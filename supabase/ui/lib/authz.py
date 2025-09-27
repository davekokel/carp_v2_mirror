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
