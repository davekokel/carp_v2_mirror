import streamlit as st
import psycopg
import urllib.parse as up
from lib.authz import require_app_access

st.set_page_config(page_title="carp v2", layout="wide", initial_sidebar_state="expanded")

def dsn_from_secrets():
    # 1) If a full connection string is provided, use it.
    if st.secrets.get("CONN"):
        return st.secrets["CONN"]

    # 2) Prefer DB_URL if present (lib.config reads st.secrets first, then .env)
    try:
        from lib.config import DB_URL
    except Exception:
        DB_URL = None
    if DB_URL:
        return DB_URL

    # 3) Otherwise compose from PG* keys in secrets (no localhost fallback)
    host = st.secrets.get("PGHOST")
    port = st.secrets.get("PGPORT", 5432)
    user = st.secrets.get("PGUSER", "postgres")
    db   = st.secrets.get("PGDATABASE", "postgres")
    pw   = st.secrets.get("PGPASSWORD", "")
    ssl  = st.secrets.get("PGSSLMODE", "require")

    if not host:
        st.error("Database host not configured. Provide DB_URL or set PGHOST in secrets.")
        st.stop()

    return f"postgresql://{user}:{up.quote(pw)}@{host}:{port}/{db}?sslmode={ssl}"

DSN = dsn_from_secrets()

host = port = user = db = "?"
try:
    with psycopg.connect(DSN) as conn, conn.cursor() as cur:
        cur.execute("select inet_server_addr()::text, inet_server_port(), current_user, current_database()")
        host, port, user, db = cur.fetchone()
    st.sidebar.success(f"DB: {host}:{port} • {user} → {db}")
except Exception as e:
    st.sidebar.error("DB connection failed")
    st.sidebar.write(str(e))

require_app_access("🔐 CARP — Private")

st.success("✅ UI is rendering")
st.write("ENV:", st.secrets.get("ENV_NAME", "(unset)"))
st.write("has CONN:", bool(st.secrets.get("CONN")))

WRITES_ENABLED = bool(st.secrets.get("WRITES_ENABLED", False))
if not WRITES_ENABLED:
    st.warning("Writes are disabled for this environment.")