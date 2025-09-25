# streamlit_app.py
import os, sys, platform, json, time
import streamlit as st

st.set_page_config(page_title="CARP – diag", layout="wide")
st.title("CARP – minimal diagnostic")

# --- What secrets/env are visible? (no values leaked, just booleans) ---
def _has(k): 
    try: return bool(st.secrets.get(k))
    except Exception: return False

cols = st.columns(4)
with cols[0]: st.metric("Python", sys.version.split()[0])
with cols[1]: st.metric("Platform", platform.system())
with cols[2]: st.metric("Has CONN", str(_has("CONN")))
with cols[3]: st.metric("Has PGHOST", str(_has("PGHOST")))

st.caption("If both CONN and PGHOST are False, set **Secrets** in Streamlit Cloud.")

# --- Show repo files (first level) so we know Cloud checked out the right app ---
with st.expander("Repo tree (first level)"):
    st.write(sorted([p for p in os.listdir(".") if not p.startswith(".")]))

# --- Choose DSN source ---
dsn = None
try:
    dsn = st.secrets.get("CONN")
except Exception:
    pass

build_from_parts = False
if not dsn:
    build_from_parts = True
    try:
        host = st.secrets["PGHOST"]
        user = st.secrets["PGUSER"]
        pwd  = st.secrets["PGPASSWORD"]
        db   = st.secrets.get("PGDATABASE", "postgres")
        port = str(st.secrets.get("PGPORT", "5432"))
        dsn  = f"postgresql+psycopg://{user}:{pwd}@{host}:{port}/{db}?sslmode=require"
        build_from_parts = False
    except Exception:
        pass

left, right = st.columns([2,1])
with left:
    st.text_input("Effective DSN (masked for display)", 
                  value=("set via CONN" if st.secrets.get("CONN") else 
                         "built from PG* parts" if dsn and not build_from_parts else 
                         "(none)"),
                  disabled=True)

with right:
    st.write("ENV_NAME:", st.secrets.get("ENV_NAME", "(unset)"))

st.divider()

# --- Attempt DB connect only when you click, with short timeout ---
try:
    from sqlalchemy import create_engine, text
    have_sqlalchemy = True
except Exception as e:
    have_sqlalchemy = False
    st.error(f"SQLAlchemy import failed: {e}")

if not dsn:
    st.warning("No DSN could be constructed. In Streamlit Cloud **Secrets**, set either:\n"
               "- `CONN = postgresql+psycopg://USER:PASSWORD@HOST:PORT/DB?sslmode=require`, or\n"
               "- `PGHOST, PGPORT, PGUSER, PGPASSWORD, PGDATABASE` (we'll build the DSN).")
elif not have_sqlalchemy:
    st.stop()

colA, colB = st.columns([1,3])
with colA:
    go = st.button("Test DB connect (5s timeout)")
with colB:
    st.caption("This won’t block page render; it just runs a tiny query on click.")

if go:
    t0 = time.time()
    try:
        engine = create_engine(
            dsn,
            pool_pre_ping=True,
            future=True,
            connect_args={
                "connect_timeout": 5,      # fail fast
                "prepare_threshold": None  # avoid DuplicatePreparedStatement
            },
        )
        with engine.connect() as cx:
            ver = cx.execute(text("select version()")).scalar()
            who = cx.execute(text("select current_user")).scalar()
            today = cx.execute(text("select current_date")).scalar()
        st.success(f"Connected as **{who}**; server {str(ver).split()[0]} ; date={today}")
    except Exception as e:
        st.error(f"DB connect/query failed after {time.time()-t0:.1f}s:\n\n{type(e).__name__}: {e}")

st.divider()
st.caption("If this page shows immediately but the full app still spins, something in your app is doing network work at import time. Move DB calls inside callbacks/buttons or functions, and keep timeouts short.")