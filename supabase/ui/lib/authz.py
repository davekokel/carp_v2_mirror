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
# --- appended: minimal logout button for Streamlit auth ---
def logout_button(label: str = "Log out") -> None:
    """
    Simple logout: flip the auth flag (if used by require_app_access) and rerun.
    Safe no-op if the flag isn't present.
    """
    import streamlit as st
    if st.button(label, key="logout_btn_main"):
        # Common session keys used by simple app-lock patterns
        for k in list(st.session_state.keys()):
            if k in ("_auth_ok", "_app_unlocked") or k.startswith("_auth_"):
                st.session_state.pop(k, None)
        # Also clear any cached password field (common patterns)
        st.session_state.pop("app_password_input", None)
        st.experimental_rerun()


def logout_button(location: str = "main", *, label: str = "Log out", key: str | None = None) -> None:
    """
    Render a logout button in either the sidebar or main area.
    - location: "sidebar" or "main"
    - label: button label text (default "Log out")
    - key: optional unique key; if omitted we derive one from location
    """
    import streamlit as st
    # Choose placement
    container = st.sidebar if str(location).lower() == "sidebar" else st
    # Ensure unique key
    k = key or f"logout_btn_{str(location).lower()}"
    if container.button(label, key=k):
        # Clear common session-state flags used by app-lock
        for sk in list(st.session_state.keys()):
            if sk in ("_auth_ok", "_app_unlocked") or sk.startswith("_auth_"):
                st.session_state.pop(sk, None)
        st.session_state.pop("app_password_input", None)
        st.experimental_rerun()


def logout_button(location: str = "main", *, label: str = "Log out", key: str | None = None) -> None:
    """
    Render a logout button in either the sidebar or main area.
    - location: "sidebar" or "main"
    - label: button label text (default "Log out")
    - key: optional unique key; if omitted we derive one from location + caller page
    Also: if another call already rendered the same key, this call is a no-op.
    """
    import os, inspect
    import streamlit as st

    # figure out the caller page name to keep keys unique per page
    try:
        caller = inspect.stack()[1].filename
        page = os.path.splitext(os.path.basename(caller))[0]
    except Exception:
        page = "unknown"

    derived = f"logout_btn_{str(location).lower()}_{page}"
    k = key or derived

    # If we've already rendered this button key on this run, skip re-registering
    sentinel = f"__rendered_{k}"
    if st.session_state.get(sentinel):
        return

    container = st.sidebar if str(location).lower() == "sidebar" else st
    if container.button(label, key=k):
        for sk in list(st.session_state.keys()):
            if sk in ("_auth_ok", "_app_unlocked") or sk.startswith("_auth_"):
                st.session_state.pop(sk, None)
        st.session_state.pop("app_password_input", None)
        st.experimental_rerun()

    st.session_state[sentinel] = True

