from __future__ import annotations

import os, re, time, hashlib, pathlib, importlib.metadata as md
import sys
sys.path.append(str(pathlib.Path(__file__).resolve().parents[3]))

import streamlit as st
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.engine.url import make_url

from carp_app.lib.db import get_engine
from carp_app.ui.lib.env_badge import show_env_badge, _env_from_db_url
from carp_app.lib.secret import env_info
from carp_app.lib.config import DB_URL

AUTH_MODE = os.getenv("AUTH_MODE", "off").lower()
if AUTH_MODE == "on":
    from carp_app.ui.auth_gate import require_auth
    sb, session, user = require_auth()
else:
    sb = session = user = None

st.set_page_config(page_title="CARP — Welcome", page_icon="👋", layout="wide")

_src = pathlib.Path(__file__).resolve()
try:
    st.caption("SRC=" + str(_src) + " • SHA256=" + hashlib.sha256(_src.read_bytes()).hexdigest()[:12] + " • DSNCHK=v3")
except Exception:
    ...

def _connect_with_retry(eng, tries: int = 5, base_delay: float = 0.5, max_delay: float = 4.0):
    last = None
    for i in range(tries):
        try:
            return eng.connect()
        except OperationalError as e:
            last = e
            time.sleep(min(max_delay, base_delay * (2 ** i)))
    raise last

def _view_exists(conn, schema: str, name: str) -> bool:
    q = text("""
      select exists (
        select 1
        from information_schema.views
        where table_schema = :s and table_name = :n
      )
    """)
    return bool(conn.execute(q, {"s": schema, "n": name}).scalar())

issues: list[str] = []
meta = ""

try:
    eng = get_engine()
    with _connect_with_retry(eng) as conn:
        row = conn.execute(text("""
            select
              inet_server_addr()::text as server,
              current_database() as db,
              current_user as usr,
              current_setting('TimeZone') as tz,
              current_setting('search_path') as sp
        """)).mappings().one()

        exts = set(conn.execute(text("""
            select extname
            from pg_extension
            where extname in ('pgcrypto','uuid-ossp')
        """)).scalars().all())

    if not DB_URL:
        issues.append("DB_URL not set")

    u = make_url(DB_URL or "")
    host = (u.host or "")
    user_in_dsn = (u.username or "")
    is_pooler_host = "pooler.supabase.com" in host

    if is_pooler_host:
        if not user_in_dsn.startswith("postgres.") or len(user_in_dsn.split(".", 1)) != 2:
            issues.append(f"Pooler DSN user should be 'postgres.<project-ref>', got '{user_in_dsn or '<empty>'}'")
        if "sslmode=require" not in (DB_URL or ""):
            issues.append("Pooler URL missing sslmode=require")
    else:
        if user_in_dsn and user_in_dsn != "postgres":
            issues.append(f"Direct DSN user should be 'postgres', got '{user_in_dsn}'")

    required_exts = {"pgcrypto", "uuid-ossp"}
    missing = sorted(required_exts - exts)
    if missing:
        issues.append("Missing extensions: " + ", ".join(missing))

    env_label = "LOCAL" if "pooler.supabase.com" not in (host or "") else "REMOTE"
    meta = f"{env_label} • db={row['db']} • user={row['usr']} • tz={row['tz']}"

    if issues:
        st.error("Health check failed:\n- " + "\n- ".join(issues))
    else:
        st.success("All checks passed")
    st.caption(meta)

except Exception as e:
    st.error(f"Health check error: {type(e).__name__}: {e}")

REQUIRED_VIEWS = [
    ("public", "v_fish"),
    ("public", "v_tanks"),
    ("public", "v_crosses"),
    ("public", "v_clutch_instances"),
    ("public", "v_clutch_treatments"),
]

missing_required: list[str] = []
try:
    with _connect_with_retry(get_engine()) as conn:
        for sch, name in REQUIRED_VIEWS:
            if not _view_exists(conn, sch, name):
                missing_required.append(f"{sch}.{name}")
except Exception as e:
    st.error(f"View check error: {type(e).__name__}: {e}")

if missing_required:
    st.error("Missing required views:\n- " + "\n- ".join(missing_required))
else:
    st.success("All required views are present")

st.title("👋 Welcome to CARP")
show_env_badge()
_env, _proj, _host, _mode = env_info()

st.write("Browse live data, upload CSVs, and print labels. Use the left sidebar to navigate.")

m = re.match(r".*://([^:@]+)@([^/?]+)", DB_URL or "")
_pguser = m.group(1) if m else os.getenv("PGUSER", "")
_env2, _proj2, _host2 = _env_from_db_url(DB_URL or "")
env_name = _env2 or _env
mode = os.getenv("APP_MODE") or ("readonly" if _pguser.endswith("_ro") else "write")

c1, c2, c3 = st.columns(3)
with c1: st.metric("Environment", env_name or "—")
with c2: st.metric("Mode", _mode or mode or "—")
with c3: st.metric("Database host", (_host2 or _host or "—"))

st.divider()

is_readonly = (mode != "write") or _pguser.endswith("_ro")
if is_readonly:
    st.info("This deployment is read-only. You can explore data and print labels.")
else:
    st.success("Uploads and edits are enabled in this deployment.")

build = os.getenv("APP_COMMIT", "unknown")
deps = f"SQLAlchemy {md.version('SQLAlchemy')} • Streamlit {md.version('streamlit')}"
st.caption(f"Build: {build} • Deps: {deps}")

with st.expander("⚙️ DB Trigger & Constraint Status (debug)"):
    try:
        with get_engine().connect() as conn:
            result = conn.execute(text("""
                select
                  (select count(*)
                     from pg_trigger t
                     join pg_class c on t.tgrelid=c.oid
                    where c.relname='fish'
                      and t.tgenabled='O'
                      and t.tgname like '%fish_autotank%') as autotank_triggers,
                  (select pg_get_constraintdef(oid)
                     from pg_constraint
                    where to_regclass('public.containers') is not null
                    order by 1 asc
                    limit 1) as containers_any_constraint
            """)).mappings().one()
            st.write("Auto-tank triggers enabled:", result["autotank_triggers"])
            st.write("Sample containers constraint:")
            st.code(result["containers_any_constraint"] or "(none)")
    except Exception as e:
        st.error(f"Health query failed: {type(e).__name__}: {e}")