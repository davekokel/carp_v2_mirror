from __future__ import annotations
import os
import streamlit as st

def show_prod_banner() -> None:
    app_env = os.getenv("APP_ENV", "local").lower()
    if app_env != "production":
        return
    user = os.getenv("PGUSER", "")
    host = os.getenv("PGHOST", "")
    port = os.getenv("PGPORT", "")
    read_only = (user == "app_ro")
    title = "PRODUCTION — READ-ONLY" if read_only else "PRODUCTION — WRITE-CAPABLE"
    color = "#dc2626"
    st.markdown(
        f"""
<div style="padding:10px 14px;border-radius:8px;margin:8px 0 12px 0;background:{color}1A;border:1px solid {color};">
  <strong style="color:{color};font-size:14px;">{title}</strong>
  <span style="margin-left:12px;color:#444;">user={user} host={host} port={port}</span>
</div>
""",
        unsafe_allow_html=True,
    )