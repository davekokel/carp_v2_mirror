from __future__ import annotations
from carp_app.lib.config import engine as get_engine
from carp_app.lib.config import DB_URL
from carp_app.ui.email_otp_gate import require_email_otp
require_email_otp()

import streamlit as st
from carp_app.lib.db import get_engine, text
st.title("🩺 Health Checks")

ENGINE = get_engine()

def ro_connection():
    cx = ENGINE.connect()
    cx.execute(text("set session characteristics as transaction read only"))
    return cx

if st.button("DB ping"):
    try:
        with ro_connection() as cx:
            st.success(cx.execute(text("select 'ok'")).scalar())
    except Exception as e:
        st.exception(e)

targets = [
    ("public.v_fish_overview", "select * from public.v_fish_overview limit 1"),
    ("public.vw_fish_overview_with_label", "select * from public.vw_fish_overview_with_label limit 1"),
    ("public.plasmids", "select * from public.plasmids limit 1"),
]
for name, sql in targets:
    if st.button(f"Check {name}"):
        try:
            with ro_connection() as cx:
                cx.execute(text(sql)).fetchone()
            st.success(f"{name}: ok")
        except Exception as e:
            st.error(f"{name}: failed")
            st.exception(e)