import hashlib
import os
from typing import Optional, Dict, Any
import streamlit as st

SESSION_KEY = "app_auth_ok"

def _sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def _allowed_hash_from_secrets() -> Optional[str]:
    pw_plain = st.secrets.get("APP_PASSWORD")
    pw_hash  = st.secrets.get("APP_PASSWORD_SHA256")
    if pw_hash:
        return str(pw_hash).strip().lower()
    if pw_plain:
        return _sha256(str(pw_plain))
    return None

def require_app_access(title: Optional[str] = "🔐 Private app") -> None:
    if st.session_state.get(SESSION_KEY):
        return

    allowed_hash = _allowed_hash_from_secrets()
    if not allowed_hash:
        st.error("App is locked but no APP_PASSWORD/APP_PASSWORD_SHA256 is set in Secrets.")
        st.stop()

    st.title(title or "🔐 Private app")
    with st.form("app_login", clear_on_submit=False):
        pw = st.text_input("App password", type="password", key="app_password_input")
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
    if "READ_ONLY" in st.secrets:
        return _truthy(st.secrets.get("READ_ONLY"))
    return _truthy(os.getenv("READ_ONLY", ""))

def read_only_banner() -> None:
    if is_read_only():
        st.info("🔒 Read-only mode is ON — write actions are disabled.", icon="🔒")

def guard_writes() -> bool:
    if is_read_only():
        st.warning("Read-only mode is ON; write actions are disabled.")
        return False
    return True

def button_guard(label: str = "Submit") -> Dict[str, Any]:
    if is_read_only():
        return {"disabled": True, "help": "Disabled in read-only mode"}
    return {}

def logout_button(location: str = "main", *, label: str = "Log out", key: Optional[str] = None) -> None:
    import os, inspect
    container = st.sidebar if str(location).lower() == "sidebar" else st
    try:
        caller = inspect.stack()[1].filename
        page = os.path.splitext(os.path.basename(caller))[0]
    except Exception:
        page = "unknown"

    k = key or f"logout_btn_{str(location).lower()}_{page}"
    sentinel = f"__rendered_{k}"
    if st.session_state.get(sentinel):
        return

    if container.button(label, key=k):
        # Clear our auth flag and common patterns
        st.session_state.pop(SESSION_KEY, None)
        for sk in list(st.session_state.keys()):
            if sk in ("_auth_ok", "_app_unlocked") or sk.startswith("_auth_"):
                st.session_state.pop(sk, None)
        st.session_state.pop("app_password_input", None)
        st.rerun()

    st.session_state[sentinel] = True

def ensure_auth(title: Optional[str] = "🔐 Private app") -> None:
    # shim for older callsites; delegates to the new gate
    require_app_access(title)