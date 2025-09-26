# streamlit_app.py  —  DIAGNOSTIC HEALTH PAGE
import sys, os, platform
import streamlit as st

st.set_page_config(page_title="CARP – Health", layout="wide")
st.title("CARP · Health check")

# 1) Show basic runtime info
c1, c2, c3 = st.columns(3)
with c1: st.metric("Python", sys.version.split()[0])
with c2: st.metric("Platform", platform.platform().split('-')[0])
with c3: st.metric("PID", os.getpid())

# 2) Safely read secrets (won't crash if missing)
secrets_ok, secrets_err, secrets = False, "", {}
try:
    secrets = st.secrets  # may raise if no secrets configured
    # accessing a key will parse TOML; wrap in try
    _ = secrets.get("ENV_NAME", None)
    secrets_ok = True
except Exception as e:
    secrets_err = str(e)

st.subheader("Secrets status")
if secrets_ok:
    c1, c2, c3 = st.columns(3)
    with c1: st.write("ENV_NAME:", secrets.get("ENV_NAME", "(unset)"))
    with c2: st.write("CONN set:", bool(secrets.get("CONN")))
    with c3: st.write("PGHOST set:", bool(secrets.get("PGHOST")))
else:
    st.error(f"Secrets unavailable: {secrets_err}")
    st.stop()

# 3) Build DSN (CONN preferred; else from PG* parts)
dsn = secrets.get("CONN") or secrets.get("CONN_STAGING")
if not dsn:
    host = secrets.get("PGHOST")
    user = secrets.get("PGUSER")
    pwd  = secrets.get("PGPASSWORD")
    db   = secrets.get("PGDATABASE", "postgres")
    port = str(secrets.get("PGPORT", "5432"))
    if host and user and pwd:
        dsn = f"postgresql://{user}:{pwd}@{host}:{port}/{db}?sslmode=require"

st.subheader("Database connectivity")
if not dsn:
    st.warning("No DSN found (CONN/PG*). Add secrets on Streamlit Cloud.")
    st.stop()

# psycopg wants postgresql:// (not postgresql+psycopg://)
dsn_psycopg = dsn.replace("postgresql+psycopg://", "postgresql://")

# 4) Try connecting and read a couple values
try:
    import psycopg
    with psycopg.connect(dsn_psycopg) as conn:
        with conn.cursor() as cur:
            cur.execute("select current_user, version()")
            who, ver = cur.fetchone()
    st.success(f"Connected as '{who}'. Server: {ver.split()[0]}")
except Exception as e:
    st.error(f"DB connect failed: {e}")
    st.stop()

st.info("Health OK. Once this is green, we’ll switch back to the full app.")