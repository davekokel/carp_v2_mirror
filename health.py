import os, sys, platform, streamlit as st
st.set_page_config(page_title="Health", layout="wide")
st.success("✅ Streamlit rendered")
st.write("Python:", sys.version.split()[0], "| Platform:", platform.platform())
st.write("Repo files:", ", ".join(sorted(p for p in os.listdir('.') if not p.startswith('.'))))
c1, c2, c3 = st.columns(3)
with c1: st.metric("has CONN", bool(st.secrets.get("CONN")))
with c2: st.metric("has PGHOST", bool(st.secrets.get("PGHOST")))
with c3: st.metric("ENV_NAME", st.secrets.get("ENV_NAME", "(unset)"))

# health.py (add or replace DB section)
import streamlit as st
from sqlalchemy import create_engine, text

st.title("DB health")

host = st.secrets.get("PGHOST")
port = st.secrets.get("PGPORT", "6543")
user = st.secrets.get("PGUSER")
pwd  = st.secrets.get("PGPASSWORD")
db   = st.secrets.get("PGDATABASE", "postgres")

st.write({
    "PGHOST": host, "PGPORT": port, "PGUSER": user,
    "PGDATABASE": db, "has_pwd": bool(pwd)
})

if not all([host, port, user, pwd, db]):
    st.error("Missing one or more PG* secrets.")
    st.stop()

url = f"postgresql+psycopg://{user}:{pwd}@{host}:{port}/{db}?sslmode=require"

try:
    eng = create_engine(
        url,
        pool_pre_ping=True,
        future=True,
        connect_args={"prepare_threshold": None},  # good with pgbouncer
    )
    with eng.connect() as cx:
        who = cx.execute(text("select current_user")).scalar()
        ver = cx.execute(text("select version()")).scalar()
    st.success(f"DB OK as {who} · {ver.split()[0]}")
except Exception as e:
    # Show the raw error text for diagnose
    st.error("DB connect failed")
    st.code(str(e))