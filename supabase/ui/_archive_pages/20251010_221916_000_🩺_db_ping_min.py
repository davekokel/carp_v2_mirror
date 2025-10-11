from __future__ import annotations

import os, sys
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import streamlit as st
from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from supabase.ui.auth_gate import require_app_unlock
except Exception:
    def require_app_unlock(): ...
require_app_unlock()

import supabase.ui.lib.app_ctx as app_ctx

st.set_page_config(page_title="CARP — DB Ping (minimal)", page_icon="🩺")
st.title("🩺 DB Ping — minimal")

APP_ENV = os.getenv("APP_ENV", "local").lower()

def _pg_env_caption():
    st.caption(
        f"PG env → host={os.getenv('PGHOST','')}  "
        f"port={os.getenv('PGPORT','')}  "
        f"user={os.getenv('PGUSER','')}  "
        f"sslmode={os.getenv('PGSSLMODE','')}  "
        f"password_set={bool(os.getenv('PGPASSWORD'))}"
    )

def _urls_caption():
    st.caption(
        f"resolved DB_URL → {os.environ.get('DB_URL','<none>')!r}  "
        f"session DB_URL → {st.session_state.get('DB_URL','<none>')!r}"
    )

# Top captions (unchanged each render)
_pg_env_caption()
_urls_caption()

c1, c2, c3 = st.columns(3)
with c1:
    if st.button("Use Env (Supabase) now", use_container_width=True):
        st.session_state.pop("DB_URL", None)
        app_ctx.clear_engine_cache()
        st.rerun()
with c2:
    if st.button("Reconnect Engine", use_container_width=True):
        app_ctx.clear_engine_cache()
        st.rerun()
with c3:
    do_ping = st.button("Refresh ping", type="primary", use_container_width=True)

# Show what connect args would be (URL-first, then env fallback) — mirrors app_ctx
p = urlparse(os.environ.get("DB_URL", ""))
qs = parse_qs(p.query or "")
connect_args_echo = {
    "host": p.hostname or os.environ.get("PGHOST", ""),
    "port": int(p.port or os.environ.get("PGPORT", "5432")),
    "dbname": (p.path or "/postgres").lstrip("/") or os.environ.get("PGDATABASE", "postgres"),
    "user": p.username or os.environ.get("PGUSER", "postgres"),
    "sslmode": (qs.get("sslmode", [os.environ.get("PGSSLMODE", "require")])[0]) or "require",
    "password_set": bool(os.environ.get("PGPASSWORD", "")),
}
st.code(f"connect_args → {connect_args_echo}")

# Engine + one-line ping
try:
    eng = app_ctx.get_engine()
    dbg = app_ctx.engine_info(eng)
    st.caption(f"Engine → host={dbg.get('host')} port={dbg.get('port')} db={dbg.get('db')} user={dbg.get('usr')}")
except Exception as e:
    st.error(f"DB connect failed: {e}")
    st.stop()

if do_ping:
    try:
        with eng.begin() as cx:
            r = cx.execute(text("""
                select
                  inet_server_addr()::text as addr,
                  inet_server_port()      as port,
                  current_database()      as db,
                  session_user            as usr
            """)).mappings().first()
        st.success(f"Ping → addr={r['addr']}:{r['port']} db={r['db']} user={r['usr']}")
    except Exception as e:
        st.error(f"Ping failed: {e}")