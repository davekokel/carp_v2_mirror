# streamlit_app.py
import time, os
import streamlit as st

st.set_page_config(page_title="CARP — diag", layout="wide")
st.title("CARP — minimal diagnostic")

# Show basic env so we know page actually rendered
c1, c2 = st.columns(2)
with c1: st.metric("PYTHON", os.getenv("PYTHON_VERSION", "unknown"))
with c2: st.metric("ENV_NAME", os.environ.get("ENV_NAME", "(unset)"))

# Echo what Streamlit secrets sees (no secrets printed, just booleans)
try:
    has_conn = bool(st.secrets.get("CONN"))
    has_pghost = bool(st.secrets.get("PGHOST"))
except Exception as e:
    st.error(f"secrets unavailable: {e}")
    has_conn = has_pghost = False

st.write(f"secrets → CONN:{has_conn}  PGHOST:{has_pghost}")

st.divider()
st.write("**DB smoke test** (skips if no DSN)")

# Build a DSN from secrets if CONN not present
dsn = os.environ.get("CONN")
if not dsn:
    try:
        dsn = (
            st.secrets.get("CONN")
            or st.secrets.get("CONN_STAGING")
            or (
                lambda s: (
                    f"postgresql+psycopg://{s['PGUSER']}:{s['PGPASSWORD']}"
                    f"@{s['PGHOST']}:{s.get('PGPORT', 5432)}/{s.get('PGDATABASE','postgres')}?sslmode=require"
                ) if all(k in s for k in ("PGHOST","PGUSER","PGPASSWORD")) else None
            )(st.secrets)
        )
    except Exception:
        dsn = None

if not dsn:
    st.info("No DSN available (set CONN in Secrets or PG* parts).")
else:
    # Import SQLAlchemy lazily so if it crashes we see it here
    try:
        from sqlalchemy import create_engine, text
        eng = create_engine(dsn, pool_pre_ping=True, future=True, connect_args={"prepare_threshold": None})
        with st.spinner("Connecting…"):
            with eng.connect() as cx:
                who = cx.execute(text("select current_user")).scalar()
                ver = cx.execute(text("select version()")).scalar()
        st.success(f"DB OK: {who} @ {str(ver).split()[0]}")
    except Exception as e:
        st.error(f"DB check failed: {e}")