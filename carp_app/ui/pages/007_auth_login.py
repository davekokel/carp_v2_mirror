from __future__ import annotations
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[3]))

import os, sys
from pathlib import Path
import streamlit as st
from carp_app.lib.config import engine as get_engine, DB_URL

st.set_page_config(page_title="Sign in — Code", page_icon="🔐")

ROOT = Path(__file__).resolve().parents[3]
LOCAL_SUPABASE = Path(__file__).resolve().parents[2]
for p in (str(LOCAL_SUPABASE), str(ROOT)):
    while p in sys.path:
        try: sys.path.remove(p)
        except ValueError: break
if "supabase" in sys.modules:
    del sys.modules["supabase"]
from supabase import create_client
sys.path.insert(0, str(ROOT))

URL = os.getenv("SUPABASE_URL",""); KEY = os.getenv("SUPABASE_ANON_KEY","")
if not URL or not KEY:
    st.error("Missing SUPABASE_URL or SUPABASE_ANON_KEY"); st.stop()
sb = create_client(URL, KEY)

st.session_state.setdefault("otp_email","")
st.session_state.setdefault("otp_code","")

def send_code():
    e = (st.session_state.get("otp_email") or "").strip()
    if not e: st.warning("Enter your email first."); return
    try:
        sb.auth.sign_in_with_otp({"email": e, "options": {"should_create_user": True}})
        st.info(f"Code sent to {e}. Check your inbox.")
    except Exception as ex:
        st.error(f"Could not send code: {ex}")

def verify_code():
    e = (st.session_state.get("otp_email") or "").strip()
    c = (st.session_state.get("otp_code") or "").strip().replace(" ","")
    if not e or not c: st.warning("Enter your email and the code."); return
    try:
        sb.auth.verify_otp({"email": e, "token": c, "type": "email"})
        sess = sb.auth.get_session()
        at = getattr(sess, "access_token", None)
        rt = getattr(sess, "refresh_token", None)
        if at and rt:
            st.session_state["sb_tokens"] = {"access": at, "refresh": rt}
        st.success(f"Signed in as {e}")
        st.switch_page("pages/001_db_ping_min.py")
    except Exception as ex:
        st.error(f"Code verification failed: {ex}")

sess = sb.auth.get_session()
usr = getattr(sess,"user",None) if sess else None
if usr:
    st.success(f"Signed in as {getattr(usr, 'email', None)}")
    st.switch_page("pages/001_db_ping_min.py")
else:
    st.title("Sign in — 6-digit code (no links)")
    st.text_input("Email address", key="otp_email", autocomplete="email")
    c1, c2, c3 = st.columns([1, 1.4, 1])
with c1:
    send = st.button("Send code", use_container_width=True)
with c2:
    st.text_input("Enter 6-digit code", key="otp_code", max_chars=8)
with c3:
    verify = st.button("Verify", type="primary", use_container_width=True)

# inline handlers (no on_click)
if send:
    send_code()
if verify:
    verify_code()
with st.expander("debug"):
    st.write({"session": sb.auth.get_session(), "tokens_in_state": st.session_state.get("sb_tokens")})
