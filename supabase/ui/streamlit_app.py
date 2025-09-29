import streamlit as st
import psycopg
import urllib.parse as up
from lib.authz import require_app_access

st.set_page_config(page_title="carp v2", layout="wide", initial_sidebar_state="expanded")

def dsn_from_secrets():
    if st.secrets.get("CONN"):
        return st.secrets["CONN"]
    host = st.secrets.get("PGHOST", "127.0.0.1")
    port = st.secrets.get("PGPORT", 54322)
    user = st.secrets.get("PGUSER", "postgres")
    db = st.secrets.get("PGDATABASE", "postgres")
    pw = st.secrets.get("PGPASSWORD", "")
    ssl = st.secrets.get("SSL_MODE", "require")
    return f"postgres://{user}:{up.quote(pw)}@{host}:{port}/{db}?sslmode={ssl}"

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