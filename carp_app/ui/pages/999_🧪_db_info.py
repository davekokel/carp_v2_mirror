from __future__ import annotations
import os, pandas as pd
import streamlit as st
from sqlalchemy import text
from carp_app.lib.db import get_engine

st.set_page_config(page_title="DB Info", page_icon="ℹ️", layout="wide")
st.title("🧪 DB connection info")

eng = get_engine()
with eng.begin() as cx:
    db, host, usr = cx.execute(text("select current_database(), inet_server_addr(), current_user")).fetchone()

st.caption(f"App DB: **{db}** @ **{host}** as **{usr}**")
st.caption(f"App DB_URL env: `{os.getenv('DB_URL')}`")
