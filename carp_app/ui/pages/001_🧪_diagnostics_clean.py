from __future__ import annotations
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[3]))

from carp_app.ui.auth_gate import require_auth
from carp_app.lib.config import engine as get_engine, DB_URL
sb, session, user = require_auth()

from carp_app.ui.email_otp_gate import require_email_otp
require_email_otp()

import os, sys, time
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import streamlit as st
import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

# Ensure repo root on path
ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from carp_app.ui.auth_gate import require_app_unlock
except Exception:
    def require_app_unlock(): ...
require_app_unlock()

# Env-only behavior: ignore any session override when not local
APP_ENV = os.getenv("APP_ENV", "local").lower()
if APP_ENV != "local":
    st.session_state.pop("DB_URL", None)

PAGE_TITLE = "CARP — Diagnostics (Clean)"
st.set_page_config(page_title=PAGE_TITLE, page_icon="🧪", layout="wide")
st.title("🧪 Diagnostics (Clean)")

# Prod banner
from carp_app.ui.lib.prod_banner import show_prod_banner
show_prod_banner()

# Normalize PG* from DB_URL so captions match reality (Supabase envs)
if APP_ENV != "local":
    p = urlparse(os.environ.get("DB_URL", ""))
    qs = parse_qs(p.query or "")
    if p.hostname: os.environ["PGHOST"] = p.hostname
    if p.port:     os.environ["PGPORT"] = str(p.port)
    os.environ["PGDATABASE"] = ((p.path or "/postgres").lstrip("/") or "postgres")
    if p.username: os.environ["PGUSER"] = p.username
    os.environ["PGSSLMODE"] = (qs.get("sslmode", ["require"])[0]) or "require"

env_line = f"PG env → host={os.getenv('PGHOST','')}  port={os.getenv('PGPORT','')}  user={os.getenv('PGUSER','')}  sslmode={os.getenv('PGSSLMODE','')}  password_set={bool(os.getenv('PGPASSWORD'))}"
urls_line = f"resolved DB_URL → {os.environ.get('DB_URL','<none>')!r}    session DB_URL → {st.session_state.get('DB_URL','<none>')!r}"
st.text(env_line + "\n" + urls_line)

# -----------------------------------------------------------------------------------
# Engine helpers
# -----------------------------------------------------------------------------------
import importlib
from carp_app.ui.lib import app_ctx as _app
importlib.reload(_app)

c1, c2 = st.columns(2)
with c1:
    if st.button("Use Env (Supabase) now", use_container_width=True):
        st.session_state.pop("DB_URL", None)
        _app.clear_engine_cache()
        st.rerun()
with c2:
    if st.button("Reconnect DB Engine", type="primary", use_container_width=True):
        _app.clear_engine_cache()
        st.rerun()

# Connect + ping
try:
    eng: Engine = _app.get_engine()
    dbg = _app.engine_info(eng)
    t0 = time.perf_counter()
    with eng.begin() as cx:
        cx.execute(text("select 1"))
    lat_ms = (time.perf_counter() - t0) * 1000.0
    with eng.begin() as cx:
        r = cx.execute(text("""
            select current_setting('server_version') as ver,
                   date_trunc('second', now() - pg_postmaster_start_time()) as uptime
        """)).mappings().first()
    ver, uptime = r["ver"], str(r["uptime"])
    st.caption(f"DB → host={dbg.get('host')}:{dbg.get('port')} db={dbg.get('db')} user={dbg.get('usr')} • version={ver} • uptime={uptime} • latency≈{lat_ms:.1f} ms")
except Exception as e:
    st.error(f"DB connect failed: {e}")
    st.stop()

# -----------------------------------------------------------------------------------
# Diagnostics
# -----------------------------------------------------------------------------------
st.subheader("Row counts")
def _counts(conn) -> pd.DataFrame:
    # Be tolerant if some views/tables are absent
    q = text("""
        with t(name, nrows) as (
          select 'fish', count(*) from public.fish
          union all select 'fish_transgene_alleles', count(*) from public.fish_transgene_alleles
          union all select 'transgene_alleles', count(*) from public.transgene_alleles
        ),
        v(name, nrows) as (
          select 'v_fish_overview', count(*) from information_schema.views
          where table_schema='public' and table_name='v_fish_overview'
        )
        select * from t
        union all
        select 'v_fish_overview_rows',
               (select count(*) from public.v_fish_overview) 
        where exists (select 1 from information_schema.views where table_schema='public' and table_name='v_fish_overview')
        order by name
    """)
    return pd.DataFrame(conn.execute(q).mappings().all())

if st.button("Refresh diagnostics", type="primary", use_container_width=True):
    try:
        with eng.begin() as cx:
            df = _counts(cx)
        st.dataframe(df, use_container_width=True)
    except Exception as e:
        st.error(f"DB connect failed: {e}")

# -----------------------------------------------------------------------------------
# Local wipe utilities
# -----------------------------------------------------------------------------------
from urllib.parse import urlparse

def _is_local_engine(conn) -> bool:
    """Runtime DB guard: allow only localhost loopback or common local datadirs."""
    row = conn.execute(text("""
        select case
                 when inet_server_addr()::text in ('127.0.0.1','::1') then true
                 when current_setting('data_directory', true) like '/opt/homebrew/var/postgresql%' then true
                 when current_setting('data_directory', true) like '/var/lib/postgresql/%'       then true
                 else false
               end as is_local
    """)).mappings().first()
    return bool(row and row["is_local"])

def _wipe_public_schema_and_reset_sequences(conn):
    """
    - TRUNCATE all public tables (RESTART IDENTITY CASCADE)
    - Reset ALL sequences in public to start at 1 (covers non-owned seqs too)
    - If helper exists, sync allele-number sequence to current max
    """
    # 1) Truncate every table in public and restart identities (owned sequences reset)
    conn.execute(text("""
    DO $wipe$
    DECLARE
      stmt text;
    BEGIN
      SELECT 'TRUNCATE TABLE ' || string_agg(format('%I.%I', schemaname, tablename), ', ')
             || ' RESTART IDENTITY CASCADE'
        INTO stmt
      FROM pg_tables
      WHERE schemaname = 'public';
      IF stmt IS NOT NULL AND length(stmt) > 0 THEN
        EXECUTE stmt;
      END IF;
    END
    $wipe$;
    """))

    # 2) Reset *all* sequences in public to start at 1 (owned or not)
    conn.execute(text("""
    DO $reset$
    DECLARE
      rec record;
    BEGIN
      FOR rec IN
        SELECT sequence_schema, sequence_name
        FROM information_schema.sequences
        WHERE sequence_schema = 'public'
      LOOP
        EXECUTE format('ALTER SEQUENCE %I.%I RESTART WITH 1', rec.sequence_schema, rec.sequence_name);
      END LOOP;
    END
    $reset$;
    """))

    # 3) If helper exists, sync allele-number seq to current max; else safe fallback to 1
    conn.execute(text("""
    DO $call$
    DECLARE
      has_helper boolean;
      has_seq    boolean;
    BEGIN
      SELECT EXISTS (
        SELECT 1
        FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname='public' AND p.proname='reset_allele_number_seq'
      ) INTO has_helper;

      IF has_helper THEN
        PERFORM public.reset_allele_number_seq();
      ELSE
        -- Fallback: if the sequence exists, set it so nextval() returns 1
        SELECT EXISTS(
          SELECT 1 FROM information_schema.sequences
          WHERE sequence_schema='public' AND sequence_name='transgene_allele_number_seq'
        ) INTO has_seq;

        IF has_seq THEN
          PERFORM setval('public.transgene_allele_number_seq', 1, false);
        END IF;
      END IF;
    END
    $call$;
    """))

# -----------------------------------------------------------------------------------
# Danger zone
# -----------------------------------------------------------------------------------
with st.expander("⚠️ Danger zone", expanded=False):
    if APP_ENV != "local":
        st.info("Danger zone is disabled outside LOCAL.")
    else:
        st.write("Wipe all data in the `public` schema (local only). Also resets all sequences.")
        agree = st.checkbox("I understand this is destructive.")
        if st.button("🧨 Wipe local DB", disabled=not agree, use_container_width=True):
            try:
                with eng.begin() as cx:
                    if not _is_local_engine(cx):
                        raise RuntimeError("Refusing to wipe: current DB is not local.")
                    _wipe_public_schema_and_reset_sequences(cx)
                st.success("✅ Public schema wiped, sequences reset, allele-number sequence synced.")
            except Exception as e:
                st.error(f"❌ Wipe failed or blocked: {type(e).__name__}: {e}")