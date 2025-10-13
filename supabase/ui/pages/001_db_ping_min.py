from supabase.ui.email_otp_gate import require_email_otp
require_email_otp()

from __future__ import annotations

import os, sys
from pathlib import Path
import streamlit as st
from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from supabase.ui.auth_gate import require_app_unlock
except Exception:
    def require_app_unlock(): ...
require_app_unlock()

APP_ENV = os.getenv("APP_ENV","local").lower()
if APP_ENV != "local":
    st.session_state.pop("DB_URL", None)

st.set_page_config(page_title="CARP — DB Ping (minimal)", page_icon="🩺")
st.title("🩺 DB Ping — minimal")
from supabase.ui.lib.prod_banner import show_prod_banner
show_prod_banner()

if APP_ENV != "local":
    from urllib.parse import urlparse, parse_qs
    p = urlparse(os.environ.get("DB_URL",""))
    qs = parse_qs(p.query or "")
    if p.hostname: os.environ["PGHOST"] = p.hostname
    if p.port:     os.environ["PGPORT"] = str(p.port)
    os.environ["PGDATABASE"] = ((p.path or "/postgres").lstrip("/") or "postgres")
    if p.username: os.environ["PGUSER"] = p.username
    os.environ["PGSSLMODE"] = (qs.get("sslmode", ["require"])[0]) or "require"

env_line  = f"PG env → host={os.getenv('PGHOST','')}  port={os.getenv('PGPORT','')}  user={os.getenv('PGUSER','')}  sslmode={os.getenv('PGSSLMODE','')}  password_set={bool(os.getenv('PGPASSWORD'))}"
urls_line = f"resolved DB_URL → {os.environ.get('DB_URL','<none>')!r}    session DB_URL → {st.session_state.get('DB_URL','<none>')!r}"
st.text(env_line + "\n" + urls_line)

from supabase.ui.lib import app_ctx as app_ctx

c1, c2, c3 = st.columns(3)
with c1:
    if st.button("Use Env (Supabase) now", width='stretch'):
        st.session_state.pop("DB_URL", None)
        app_ctx.clear_engine_cache()
        st.rerun()
with c2:
    if st.button("Reconnect Engine", type="primary", width='stretch'):
        app_ctx.clear_engine_cache()
        st.rerun()
with c3:
    do_ping = st.button("Refresh ping", width='stretch')

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
            r = cx.execute(text("select inet_server_addr()::text as addr, inet_server_port() as port, current_database() as db, session_user as usr")).mappings().first()
        st.success(f"Ping → addr={r['addr']}:{r['port']} db={r['db']} user={r['usr']}")
    except Exception as e:
        st.error(f"Ping failed: {e}")