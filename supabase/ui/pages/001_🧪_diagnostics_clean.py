from __future__ import annotations
import os, sys, time
from pathlib import Path
import streamlit as st
import pandas as pd
from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from supabase.ui.auth_gate import require_app_unlock
except Exception:
    def require_app_unlock(): ...
require_app_unlock()

# Env-only behavior: ignore any session override when not local
APP_ENV = os.getenv("APP_ENV","local").lower()
if APP_ENV != "local":
    st.session_state.pop("DB_URL", None)

PAGE_TITLE = "CARP — Diagnostics (Clean)"
st.set_page_config(page_title=PAGE_TITLE, page_icon="🧪", layout="wide")
st.title("🧪 Diagnostics (Clean)")
from supabase.ui.lib.prod_banner import show_prod_banner
show_prod_banner()

# Normalize PG* from DB_URL so captions match reality
if APP_ENV != "local":
    from urllib.parse import urlparse, parse_qs
    p = urlparse(os.environ.get("DB_URL",""))
    qs = parse_qs(p.query or "")
    if p.hostname: os.environ["PGHOST"] = p.hostname
    if p.port:     os.environ["PGPORT"] = str(p.port)
    os.environ["PGDATABASE"] = ((p.path or "/postgres").lstrip("/") or "postgres")
    if p.username: os.environ["PGUSER"] = p.username
    os.environ["PGSSLMODE"] = (qs.get("sslmode", ["require"])[0]) or "require"

env_line = f"PG env → host={os.getenv('PGHOST','')}  port={os.getenv('PGPORT','')}  user={os.getenv('PGUSER','')}  sslmode={os.getenv('PGSSLMODE','')}  password_set={bool(os.getenv('PGPASSWORD'))}"
urls_line = f"resolved DB_URL → {os.environ.get('DB_URL','<none>')!r}    session DB_URL → {st.session_state.get('DB_URL','<none>')!r}"
st.text(env_line + "\n" + urls_line)

import importlib
from supabase.ui.lib import app_ctx as _app
importlib.reload(_app)

c1, c2 = st.columns(2)
with c1:
    if st.button("Use Env (Supabase) now", width='stretch'):
        st.session_state.pop("DB_URL", None)
        _app.clear_engine_cache()
        st.rerun()
with c2:
    if st.button("Reconnect DB Engine", type="primary", width='stretch'):
        _app.clear_engine_cache()
        st.rerun()

try:
    eng = _app.get_engine()
    dbg = _app.engine_info(eng)
    lat_ms = None
    ver = ""
    uptime = ""
    t0 = time.perf_counter()
    with eng.begin() as cx:
        cx.execute(text("select 1"))
    lat_ms = (time.perf_counter() - t0) * 1000.0
    with eng.begin() as cx:
        r = cx.execute(text("select current_setting('server_version') as ver, date_trunc('second', now() - pg_postmaster_start_time()) as uptime")).mappings().first()
    ver, uptime = r["ver"], str(r["uptime"])
    st.caption(f"DB → host={dbg.get('host')}:{dbg.get('port')} db={dbg.get('db')} user={dbg.get('usr')} • version={ver} • uptime={uptime} • latency≈{lat_ms:.1f} ms")
except Exception as e:
    st.error(f"DB connect failed: {e}")
    st.stop()

st.subheader("Row counts")
def _counts(conn) -> pd.DataFrame:
    q = text("""
        with t(name, nrows) as (
          select 'fish', count(*) from public.fish
          union all select 'fish_transgene_alleles', count(*) from public.fish_transgene_alleles
          union all select 'transgene_alleles', count(*) from public.transgene_alleles
        ),
        v(name, nrows) as (
          select 'v_fish_overview', count(*) from public.v_fish_overview
        )
        select * from t union all select * from v order by name
    """)
    return pd.DataFrame(conn.execute(q).mappings().all())

if st.button("Refresh diagnostics", type="primary", width='stretch'):
    try:
        with eng.begin() as cx:
            df = _counts(cx)
        st.dataframe(df, use_container_width=True)
    except Exception as e:
        st.error(f"DB connect failed: {e}")

with st.expander("Danger zone"):
    st.write("Wipe all data in `public` schema (local only).")
    ok = st.checkbox("I understand this is destructive.")
    if st.button("🧨 Wipe local DB", disabled=not ok):
        if APP_ENV != "local":
            st.error("Refusing to wipe: not local.")
        else:
            try:
                with eng.begin() as cx:
                    cx.execute(text("""
                        DO $$
                        DECLARE stmt text;
                        BEGIN
                          SELECT 'TRUNCATE TABLE ' || string_agg(format('%I.%I', schemaname, tablename), ', ') || ' RESTART IDENTITY CASCADE'
                            INTO stmt
                          FROM pg_tables WHERE schemaname='public';
                          IF stmt IS NOT NULL THEN EXECUTE stmt; END IF;
                        END$$;
                    """))
                st.success("Local DB wiped.")
            except Exception as e:
                st.error(f"Wipe failed: {e}")
