# app.py — ultra-verbose boot check
import sys, os, socket, platform, time
import streamlit as st

st.set_page_config(page_title="CARP health", layout="wide")
st.title("CARP health")

# 0) Prove Streamlit is actually rendering
st.success("✅ UI is rendering")
st.write("Python:", sys.version.split()[0], "Platform:", platform.platform())

# 1) Show repo files (sanity that we're on the right commit)
try:
    files = sorted([p for p in os.listdir(".") if not p.startswith(".")])[:50]
    st.caption("Repo root files:")
    st.code("\n".join(files) or "(none)")
except Exception as e:
    st.error(f"Listing files failed: {e}")

# 2) Secrets — don’t crash if missing
try:
    env_name = st.secrets.get("ENV_NAME", "(unset)")
    dsn = st.secrets.get("CONN") or st.secrets.get("CONN_STAGING")
    dsn_masked = (dsn[:25] + "…") if isinstance(dsn, str) and len(dsn) > 25 else str(dsn)
    c1, c2 = st.columns(2)
    with c1: st.metric("ENV_NAME", env_name)
    with c2: st.write("DSN present:", bool(dsn), dsn_masked)
except Exception as e:
    st.error(f"Secrets unavailable: {e}")

# 3) Package availability
try:
    import sqlalchemy, psycopg, pandas
    st.write("sqlalchemy:", sqlalchemy.__version__,
             "psycopg:", psycopg.__version__,
             "pandas:", pandas.__version__)
except Exception as e:
    st.error(f"Import error: {e}")

# 4) Try DB ping (only if we have a DSN)
dsn = st.secrets.get("CONN") or st.secrets.get("CONN_STAGING")
if dsn:
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
            connect_args={"prepare_threshold": None},  # avoid prepared-stmt collisions
        )
        start = time.time()
        with engine.connect() as cx:
            ver = cx.execute(text("select version()")).scalar()
            who = cx.execute(text("select current_user")).scalar()
        st.success(f"DB OK as {who} · {ver.split()[0]}  (%.2fs)" % (time.time()-start))
    except Exception as e:
        st.exception(e)
else:
    st.warning("No DSN in secrets. Set `CONN` (or `CONN_STAGING`) in Cloud → Settings → Secrets.")

st.write("---")
st.write("If you see the green ‘UI is rendering’, blank pages aren’t a Streamlit issue. If it hangs before that, the app path is wrong or the build is still provisioning.")