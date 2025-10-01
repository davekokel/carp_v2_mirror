# supabase/ui/auth_gate.py
from __future__ import annotations
import hashlib
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
    submit = st.button("Unlock", type="primary", use_container_width=True)

    if submit:
        sha_expected = (st.secrets.get("APP_PASSWORD_SHA256") or "").strip().lower()
        sha_entered = hashlib.sha256((pw or "").encode("utf-8")).hexdigest()
        if sha_entered == sha_expected:
            st.session_state["_app_unlocked"] = True
            st.rerun()
        else:
            st.error("Incorrect passphrase.")

    st.stop()