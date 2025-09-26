# streamlit_app.py — defensive bootstrap
import sys, os, time, platform
import streamlit as st

st.set_page_config(page_title="CARP", layout="wide")

# 0) Prove Streamlit is rendering
st.title("CARP (app entry)")
st.success("✅ UI is rendering")
st.caption(f"Python {sys.version.split()[0]} · {platform.platform()}")

# 1) Secrets visibility (don’t crash if missing)
try:
    env_name = st.secrets.get("ENV_NAME", "(unset)")
    dsn = st.secrets.get("CONN") or st.secrets.get("CONN_STAGING")
    st.write("Secrets → ENV_NAME:", env_name, " · DSN present:", bool(dsn))
except Exception as e:
    st.error(f"Secrets unavailable: {e}")

# 2) Import your app modules with error surfacing
with st.spinner("Importing modules…"):
    try:
        from lib_shared import pick_environment
        from lib.db import get_engine, quick_db_check
    except Exception as e:
        st.error("❌ Import error while loading app modules:")
        st.exception(e)
        st.stop()

# 3) Optional quick DB ping if DSN provided
dsn = st.secrets.get("CONN") or st.secrets.get("CONN_STAGING")
if dsn:
    from sqlalchemy import create_engine, text
    try:
        st.info("Connecting to database…")
        engine = create_engine(
            dsn,
            pool_pre_ping=True,
            pool_size=2,
            max_overflow=0,
            future=True,
            connect_args={"prepare_threshold": None, "connect_timeout": 5},
        )
        t0 = time.time()
        with engine.connect() as cx:
            who = cx.execute(text("select current_user")).scalar()
            ver = cx.execute(text("select version()")).scalar()
        st.success(f"DB OK as {who} · {str(ver).split()[0]}  (%.2fs)" % (time.time()-t0))
    except Exception as e:
        st.error("❌ Database connection failed:")
        st.exception(e)
else:
    st.warning("No DSN found in secrets. Set `CONN` (or PGHOST/PGUSER/PGPASSWORD/PGPORT/PGDATABASE).")

st.divider()
st.write("🎯 If you see the green checks above, the core runtime is healthy. Your **Pages/** will appear in the sidebar automatically.")