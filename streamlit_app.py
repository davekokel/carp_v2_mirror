# streamlit_app.py — ultra-safe boot + DB diag
import os, sys, platform, time
import streamlit as st

st.set_page_config(page_title="CARP", layout="wide")

st.title("CARP — Boot & DB diagnostics")

# --- Always render something first ---
c1, c2, c3, c4 = st.columns(4)
with c1: st.metric("Python", sys.version.split()[0])
with c2: st.metric("Platform", platform.system())
with c3: st.metric("ENV_NAME", str(st.secrets.get("ENV_NAME","(unset)")))
with c4: st.metric("Has CONN", "yes" if st.secrets.get("CONN") else "no")

# Show secrets presence (not values)
st.caption("Secrets present → "
           f"CONN:{bool(st.secrets.get('CONN'))} "
           f"PGHOST:{bool(st.secrets.get('PGHOST'))} "
           f"PGUSER:{bool(st.secrets.get('PGUSER'))} "
           f"PGDATABASE:{bool(st.secrets.get('PGDATABASE'))}")

# Masked preview of CONN
def _mask_conn(s: str) -> str:
    if not s: return "(missing)"
    # keep scheme and host; mask credentials
    try:
        before_at = s.split("@", 1)[0]
        after_at  = s.split("@", 1)[1]
        scheme = before_at.split("://",1)[0]
        return f"{scheme}://***:***@{after_at}"
    except Exception:
        return "(unparseable)"

st.write("CONN (masked):", _mask_conn(st.secrets.get("CONN","")))

# ---- Try DB connection, but never crash the page ----
status = st.empty()
status.info("Connecting to database...")

err_box = st.empty()
ok_box  = st.empty()

try:
    from sqlalchemy import create_engine, text
    dsn = st.secrets.get("CONN")
    if not dsn:
        # Optional fallback from PG*; also make password URL-safe
        from urllib.parse import quote_plus
        host = st.secrets.get("PGHOST")
        user = st.secrets.get("PGUSER")
        pwd  = st.secrets.get("PGPASSWORD")
        db   = st.secrets.get("PGDATABASE","postgres")
        port = str(st.secrets.get("PGPORT","5432"))
        if host and user and pwd:
            dsn = f"postgresql+psycopg://{user}:{quote_plus(pwd)}@{host}:{port}/{db}?sslmode=require"

    if not dsn:
        raise RuntimeError("No DSN. Provide CONN in Secrets (or PG* parts).")

    engine = create_engine(
        dsn,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=5,
        pool_recycle=1800,
        future=True,
        connect_args={"prepare_threshold": None},  # avoid DuplicatePreparedStatement
    )

    with engine.connect() as cx:
        who = cx.execute(text("select current_user")).scalar()
        ver = cx.execute(text("select version()")).scalar()
        status.success("DB connected ✅")
        ok_box.write(f"**current_user:** `{who}`")
        ok_box.write(f"**version:** `{str(ver).split()[0]}`")

except Exception as e:
    status.error("DB connection failed")
    err_box.exception(e)

st.divider()
st.write("If this page renders but DB fails, fix the app secrets (CONN).")