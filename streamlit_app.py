# streamlit_app.py (repo root)
import os
import traceback
import streamlit as st

# Optional: turn on a simple debug panel
DEBUG = st.sidebar.checkbox("Show debug info", value=True)

st.set_page_config(page_title="CARP", layout="wide")
st.title("CARP")

# --- 1) Secrets / env detection ------------------------------------------------
def _get(k, default=None):
    # Use st.secrets when present; fallback to env for local debugging
    try:
        return st.secrets.get(k, default)
    except Exception:
        return os.getenv(k, default)

dsn = (_get("CONN") or _get("CONN_STAGING") or _get("CONN_LOCAL"))
pg_parts = {
    "PGHOST": _get("PGHOST"),
    "PGPORT": _get("PGPORT"),
    "PGUSER": _get("PGUSER"),
    "PGPASSWORD": _get("PGPASSWORD"),
    "PGDATABASE": _get("PGDATABASE", "postgres"),
}
env_name = _get("ENV_NAME", "(unset)")
sb_url = _get("SUPABASE_URL")
sb_key = _get("SUPABASE_KEY")

with st.expander("Status", expanded=True):
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("ENV_NAME", env_name)
        st.metric("Has DSN (CONN…)", bool(dsn))
    with c2:
        st.metric("Has PGHOST/USER/PASS", bool(pg_parts["PGHOST"] and pg_parts["PGUSER"] and pg_parts["PGPASSWORD"]))
        st.metric("Has PGDATABASE", bool(pg_parts["PGDATABASE"]))
    with c3:
        st.metric("Has SUPABASE_URL", bool(sb_url))
        st.metric("Has SUPABASE_KEY", bool(sb_key))

if DEBUG:
    with st.expander("Raw values (masked)"):
        st.json({
            "ENV_NAME": env_name,
            "CONN?(bool)": bool(dsn),
            "PG* present?": {k: bool(v) for k, v in pg_parts.items()},
            "SUPABASE_URL?": bool(sb_url),
            "SUPABASE_KEY?": bool(sb_key),
        })

# --- 2) DB connectivity check (via your lib/db) --------------------------------
# We try to import after rendering some UI so blank page never happens.
db_ok = False
db_msg = "Not attempted"

try:
    from lib.db import get_engine, quick_db_check  # uses st.secrets internally

    # Prefer DSN if provided via secrets
    engine = get_engine(dsn if dsn else None)
    db_msg = quick_db_check(engine)
    db_ok = db_msg.startswith("OK:")
except Exception as e:
    db_msg = f"DB check failed: {e.__class__.__name__}: {e}"
    if DEBUG:
        st.code(traceback.format_exc())

st.subheader("Database")
if db_ok:
    st.success(db_msg)
else:
    st.error(db_msg)
    st.info(
        "Set **CONN** in Streamlit Secrets (recommended), e.g.\n\n"
        '```toml\nCONN = "postgresql+psycopg://USER:PASS@HOST:PORT/postgres?sslmode=require"\nENV_NAME = "staging"\n```'
        "\n—or supply **PGHOST, PGUSER, PGPASSWORD, PGPORT, PGDATABASE**."
    )

# --- 3) Links to pages ---------------------------------------------------------
st.subheader("Pages")
st.write("Use the left sidebar, or quick links:")
st.page_link("pages/01_Overview.py", label="Overview")
st.page_link("pages/02_Assign_and_Labels.py", label="Assign & Labels")
st.page_link("pages/02_Details.py", label="Details")
st.page_link("pages/09_seed_loader.py", label="Seed Loader")

st.caption("If the app still shows a blank page on Cloud, open **App → Logs**; "
           "with this file you should always see an error message on-screen instead of a blank page.")