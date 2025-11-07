from __future__ import annotations
import os
import streamlit as st
from sqlalchemy import text
from carp_app.lib.db import get_engine

st.set_page_config(page_title="🩺 Health", page_icon="🩺", layout="wide")
st.title("🩺 Connection health")

eng = get_engine()
with eng.begin() as cx:
    r = cx.execute(text("select inet_server_addr(), current_database(), current_user")).first()

st.subheader("Effective endpoint")
st.code({"server_addr": str(r[0]), "database": str(r[1]), "db_user": str(r[2])})

st.subheader("Relevant env")
st.code({
    "DB_URL": os.getenv("DB_URL", ""),
    "PGHOST": os.getenv("PGHOST", ""),
    "PGPORT": os.getenv("PGPORT", ""),
    "PGUSER": os.getenv("PGUSER", ""),
    "PGDATABASE": os.getenv("PGDATABASE", ""),
    "PGSSLMODE": os.getenv("PGSSLMODE", ""),
    "POOLER_AUTOREWRITE": os.getenv("POOLER_AUTOREWRITE", "1"),
})
