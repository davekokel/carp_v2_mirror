from __future__ import annotations

import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[3]))

import os, re, time
import streamlit as st
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from carp_app.lib.db import get_engine
from carp_app.ui.lib.env_badge import show_env_badge, _env_from_db_url
from carp_app.lib.secret import env_info

AUTH_MODE = os.getenv("AUTH_MODE", "off").lower()
if AUTH_MODE == "on":
    from carp_app.ui.auth_gate import require_auth
    sb, session, user = require_auth()
else:
    sb = session = user = None

st.set_page_config(page_title="CARP — Welcome", page_icon="👋", layout="wide")

def _env_from_url(url: str) -> str:
    if "pooler.supabase.com" in url:
        if "aws-1-us-west-1.pooler.supabase.com" in url: return "STAGING"
        if "aws-1-us-east-2.pooler.supabase.com" in url: return "PROD"
        if "aws-0-us-east-2.pooler.supabase.com" in url: return "PROD"
        if "aws-0-us-east-1.pooler.supabase.com" in url: return "PROD"
        return "REMOTE"
    return "LOCAL"

def _connect_with_retry(eng, tries: int = 5, base_delay: float = 0.5, max_delay: float = 4.0):
    last = None
    for i in range(tries):
        try:
            return eng.connect()
        except OperationalError as e:
            last = e
            time.sleep(min(max_delay, base_delay * (2 ** i)))
    raise last

DB_URL = os.getenv("DB_URL", "")
expect_pooler_user = "pooler.supabase.com" in DB_URL
issues: list[str] = []

try:
    eng = get_engine()
    with _connect_with_retry(eng) as conn:
        row = conn.execute(text("""
            select
              inet_server_addr()::text as server,
              current_database() as db,
              current_user as usr,
              current_setting('TimeZone') as tz,
              current_setting('search_path') as sp,
              version()
        """)).mappings().one()

        exts = set(conn.execute(text("""
            select extname from pg_extension
            where extname in ('pgcrypto','uuid-ossp','pg_stat_statements','pg_graphql','supabase_vault')
        """)).scalars().all())

    if expect_pooler_user and "." not in row["usr"]:
        issues.append(f"Pooler user should look like postgres.<project-ref>, got '{row['usr']}'")
    if not DB_URL:
        issues.append("DB_URL not set")
    if "pooler.supabase.com" in DB_URL and "sslmode=require" not in DB_URL:
        issues.append("Pooler URL missing sslmode=require")

    required_exts = {"pgcrypto", "uuid-ossp"}
    missing = sorted(required_exts - exts)
    if missing:
        issues.append(f"Missing extensions: {', '.join(missing)}")

    env_label = _env_from_url(DB_URL)
    meta = f"{env_label} • db={row['db']} • user={row['usr']} • tz={row['tz']}"

    if issues:
        st.error("Health check failed:\n- " + "\n- ".join(issues))
    else:
        st.success("All checks passed")
    st.caption(meta)

except Exception as e:
    st.error(f"Health check error: {type(e).__name__}: {e}")

required_views = [
    ("public", "v_fish_overview"),
    ("public", "v_containers_overview"),
    ("public", "v_crosses_status"),
    ("public", "v_clutch_instances_overview"),
]

missing_views: list[str] = []
try:
    with _connect_with_retry(get_engine()) as conn:
        rows = conn.execute(text("""
            select table_schema, table_name
            from information_schema.views
            where (table_schema, table_name) in :pairs
        """), {"pairs": tuple(required_views)}).fetchall()
        present = {(r[0], r[1]) for r in rows}
        for pair in required_views:
            if pair not in present:
                missing_views.append(f"{pair[0]}.{pair[1]}")
except Exception as e:
    st.error(f"View check error: {type(e).__name__}: {e}")

if missing_views:
    st.error("Missing required views:\n- " + "\n- ".join(missing_views))
else:
    st.success("All required views are present")

st.title("👋 Welcome to CARP")
show_env_badge()
_env, _proj, _host, _mode = env_info()

st.write("Browse live data, upload CSVs, and print labels — no install needed. Use the left sidebar to navigate.")

m = re.match(r".*://([^:@]+)@([^/?]+)", DB_URL)
_pguser = m.group(1) if m else os.getenv("PGUSER", "")
_env2, _proj2, _host2 = _env_from_db_url(DB_URL)
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
st.caption(f"Build: {build}")