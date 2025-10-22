from __future__ import annotations

# --- sys.path prime so relative imports work in Streamlit ---
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[3]))

# --- std/3p imports ---
import os, time
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import pandas as pd
import streamlit as st
from sqlalchemy import text
from sqlalchemy.engine import Engine

# --- app imports ---
from carp_app.lib.config import DB_URL
from carp_app.ui.lib.env_badge import _env_from_db_url
from carp_app.ui.lib.prod_banner import show_prod_banner

# Auth gates
from carp_app.ui.auth_gate import require_auth
sb, session, user = require_auth()
from carp_app.ui.email_otp_gate import require_email_otp
require_email_otp()

# Ensure repo root on sys.path
ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ------------------------------------------------------------------------------------
# Environment detection & kill-switches
# ------------------------------------------------------------------------------------
_env, _proj, _host = _env_from_db_url(DB_URL)
IS_LOCAL = (_env == "LOCAL") or ("sslmode=disable" in DB_URL) or (_host in {"127.0.0.1", "localhost"})

def _assert_local_or_die() -> None:
    """Server-side hard stop for any destructive action outside LOCAL."""
    if not IS_LOCAL:
        st.error("Danger zone is disabled in this deployment (not LOCAL).")
        st.stop()

# Normalize PG* env to match DB_URL for captions (esp. Supabase pooler)
if not IS_LOCAL:
    p = urlparse(DB_URL or "")
    qs = parse_qs(p.query or "")
    if p.hostname: os.environ["PGHOST"] = p.hostname
    if p.port:     os.environ["PGPORT"] = str(p.port)
    os.environ["PGDATABASE"] = ((p.path or "/postgres").lstrip("/") or "postgres")
    if p.username: os.environ["PGUSER"] = p.username
    os.environ["PGSSLMODE"] = (qs.get("sslmode", ["require"])[0]) or "require"
else:
    # Local devs commonly rely on libpq defaults; leave as-is
    pass

# If not local, never honor a session DB_URL override
if not IS_LOCAL:
    st.session_state.pop("DB_URL", None)

# ------------------------------------------------------------------------------------
# Page chrome
# ------------------------------------------------------------------------------------
st.set_page_config(page_title="CARP — Diagnostics (Clean)", page_icon="🧪", layout="wide")
st.title("🧪 Diagnostics (Clean)")
show_prod_banner()

env_line = (
    f"PG env → host={os.getenv('PGHOST','')}  port={os.getenv('PGPORT','')}  "
    f"user={os.getenv('PGUSER','')}  sslmode={os.getenv('PGSSLMODE','require')}  "
    f"password_set={bool(os.getenv('PGPASSWORD'))}"
)
urls_line = f"resolved DB_URL → {os.environ.get('DB_URL','<none>')!r}    session DB_URL → {st.session_state.get('DB_URL','<none>')!r}"
st.text(env_line + "\n" + urls_line)

# ------------------------------------------------------------------------------------
# Engine helpers
# ------------------------------------------------------------------------------------
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
    st.caption(
        f"DB → host={dbg.get('host')}:{dbg.get('port')} db={dbg.get('db')} user={dbg.get('usr')} "
        f"• version={ver} • uptime={uptime} • latency≈{lat_ms:.1f} ms"
    )
except Exception as e:
    st.error(f"DB connect failed: {e}")
    st.stop()

# ------------------------------------------------------------------------------------
# Diagnostics
# ------------------------------------------------------------------------------------
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
          select 'v_fish', count(*) from information_schema.views
          where table_schema='public' and table_name='v_fish'
        )
        select * from t
        union all
        select 'v_fish_overview_rows',
               (select count(*) from public.v_fish)
        where exists (
          select 1 from information_schema.views
          where table_schema='public' and table_name='v_fish'
        )
        order by name
    """)
    return pd.DataFrame(conn.execute(q).mappings().all())

if st.button("Refresh diagnostics", type="primary", use_container_width=True):
    try:
        with eng.begin() as cx:
            df = _counts(cx)
        st.dataframe(df, use_container_width=True)
    except Exception as e:
        st.error(f"Diagnostics failed: {e}")

# ------------------------------------------------------------------------------------
# Local-only wipe utilities (guarded twice: env + runtime)
# ------------------------------------------------------------------------------------
def _is_local_engine(conn) -> bool:
    """Runtime DB guard: allow only loopback/typical local datadirs."""
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

# ------------------------------------------------------------------------------------
# Danger zone (locked on non-LOCAL)
# ------------------------------------------------------------------------------------
with st.expander("⚠️ Danger zone", expanded=False):
    if not IS_LOCAL:
        st.info("This deployment is **not LOCAL** — wipe controls are disabled by policy.")
        st.button("Wipe disabled (non-LOCAL)", use_container_width=True, disabled=True, key="wipe_disabled")
    else:
        st.write("Wipe all data in the `public` schema (LOCAL only). Also resets all sequences.")
        ack1 = st.checkbox("I understand this is **destructive**.")
        ack2 = st.text_input("Type `wipe local` to confirm:")
        do_wipe = st.button(
            "🧨 Wipe local DB",
            use_container_width=True,
            type="primary",
            disabled=not (ack1 and ack2.strip().lower() == "wipe local"),
        )
        if do_wipe:
            try:
                _assert_local_or_die()  # env kill-switch
                with eng.begin() as cx:
                    if not _is_local_engine(cx):  # runtime safety net
                        raise RuntimeError("Refusing to wipe: current DB is not local.")
                    _wipe_public_schema_and_reset_sequences(cx)
                st.success("✅ Public schema wiped; sequences reset.")
            except Exception as e:
                st.error(f"❌ Wipe blocked/failed: {type(e).__name__}: {e}")