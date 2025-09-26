# app.py — CARP health (single-file)
import os, sys, time, platform
import streamlit as st

st.set_page_config(page_title="CARP health", layout="wide")
st.title("CARP health")

# 0) Prove Streamlit is rendering
st.success("✅ UI is rendering")
st.caption(f"Python {sys.version.split()[0]} · {platform.platform()}")

# 1) Repo files (sanity that we’re on the expected commit)
try:
    files = sorted(p for p in os.listdir(".") if not p.startswith("."))[:50]
    with st.expander("Repo root files (first 50)"):
        st.code("\n".join(files) or "(none)")
except Exception as e:
    st.error(f"Listing files failed: {e}")

# 2) Secrets — don’t crash if missing
try:
    env_name = st.secrets.get("ENV_NAME", "(unset)")
    conn_from_secrets = st.secrets.get("CONN") or st.secrets.get("CONN_STAGING")
    with st.container():
        c1, c2, c3 = st.columns(3)
        c1.metric("ENV_NAME", env_name)
        c2.metric("has CONN", str(bool(conn_from_secrets)))
        c3.metric("has PGHOST", str(bool(st.secrets.get('PGHOST'))))
except Exception as e:
    st.error(f"Secrets unavailable: {e}")

# 3) Build DSN: prefer CONN; fallback to PG* parts
dsn = None
try:
    dsn = st.secrets.get("CONN") or st.secrets.get("CONN_STAGING")
    if not dsn:
        host = st.secrets.get("PGHOST")
        user = st.secrets.get("PGUSER")
        pwd  = st.secrets.get("PGPASSWORD")
        db   = st.secrets.get("PGDATABASE", "postgres")
        port = str(st.secrets.get("PGPORT", "5432"))
        if host and user and pwd:
            dsn = f"postgresql+psycopg://{user}:{pwd}@{host}:{port}/{db}?sslmode=require"
except Exception:
    dsn = None

if not dsn:
    st.error("No DSN found. Set `CONN` (or PGHOST/PGUSER/PGPASSWORD/PGDATABASE/PGPORT) in **Secrets**.")
    st.stop()

# 4) Packages (quick sanity)
try:
    import sqlalchemy, psycopg, pandas  # noqa
    st.caption(f"sqlalchemy {sqlalchemy.__version__} · psycopg {psycopg.__version__} · pandas {pandas.__version__}")
except Exception as e:
    st.warning(f"Import check failed: {e}")

# 5) DB ping
try:
    from sqlalchemy import create_engine, text
    st.info("Connecting to DB…")
    engine = create_engine(
        dsn,
        pool_pre_ping=True,
        pool_size=2,
        max_overflow=0,
        pool_recycle=1200,
        future=True,
        connect_args={
            # Avoid server-side prepared statements that can collide on Cloud
            "prepare_threshold": None,
            # Gentle timeout so a bad DSN doesn’t ‘hang’
            "connect_timeout": 5,
        },
    )
    start = time.time()
    with engine.connect() as cx:
        who = cx.execute(text("select current_user")).scalar()
        ver = cx.execute(text("select version()")).scalar()
    st.success(f"DB OK · user={who} · {str(ver).split()[0]}  (%.2fs)" % (time.time()-start))
except Exception as e:
    st.exception(e)
    st.stop()

st.divider()
st.write("✅ Health passed; once this page is green, wire your real UI here or point Main file to it.")