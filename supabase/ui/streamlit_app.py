# supabase/ui/streamlit_app.py
from __future__ import annotations

import os, sys
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
import streamlit as st
from sqlalchemy import text

# --- Robust import path so this works locally and in cloud runners ---
ROOT = Path(__file__).resolve().parents[3]  # …/carp_v2
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# 🔒 auth gate
try:
    from supabase.ui.auth_gate import require_app_unlock
except Exception:
    def require_app_unlock(): ...
require_app_unlock()

# Centralized engine helpers
from supabase.ui.lib.app_ctx import get_engine, engine_info, set_db_url

PAGE_TITLE = "CARP — Home / Diagnostics"
st.set_page_config(page_title=PAGE_TITLE, page_icon="🧪", layout="wide")
st.title("🧪 CARP — Diagnostics")

# -----------------------------------------------------------------------------
# DB target selector (Local / Env/Default / Custom)
# -----------------------------------------------------------------------------
DEFAULT_LOCAL = "postgresql://postgres@127.0.0.1:5432/postgres?sslmode=disable"

choice_map = {
    "Local (localhost)": "local",
    "Env/Default": "env",
    "Custom": "custom",
}
reverse_choice = {v: k for k, v in choice_map.items()}

sel_key = st.session_state.get("db_choice", "local")
radio = st.radio(
    "Choose DB target",
    list(choice_map.keys()),
    index=list(choice_map.keys()).index(reverse_choice.get(sel_key, "Local (localhost)")),
    horizontal=True,
)

choice = choice_map[radio]
custom_default = st.session_state.get("db_custom", "")
custom_url = st.text_input(
    "Custom DB URL",
    value=custom_default,
    placeholder="postgresql://user:pass@host:port/db?sslmode=…",
    disabled=(choice != "custom"),
)

connect_clicked = st.button("Connect to selected DB")

def _mask_url(url: str) -> str:
    try:
        if "://" not in url:
            return url
        scheme, rest = url.split("://", 1)
        if "@" in rest and ":" in rest.split("@", 1)[0]:
            creds, hostpart = rest.split("@", 1)
            user, _pw = creds.split(":", 1)
            return f"{scheme}://{user}:***@{hostpart}"
        return url
    except Exception:
        return url

if connect_clicked:
    st.session_state["db_choice"] = choice
    if choice == "local":
        os.environ["DB_URL"] = DEFAULT_LOCAL
        st.session_state["db_custom"] = DEFAULT_LOCAL
        st.session_state["db_choice_label"] = "LOCAL • Homebrew"
    elif choice == "custom":
        if not custom_url.strip():
            st.warning("Enter a custom DB URL to connect.")
        else:
            os.environ["DB_URL"] = custom_url.strip()
            st.session_state["db_custom"] = custom_url.strip()
            st.session_state["db_choice_label"] = "CUSTOM"
    else:  # env/default
        os.environ.pop("DB_URL", None)
        st.session_state["db_custom"] = ""
        st.session_state["db_choice_label"] = "ENV/DEFAULT"
    st.rerun()

# -----------------------------------------------------------------------------
# DB connection + header diagnostic line
# -----------------------------------------------------------------------------
eng = get_engine()
dbg = engine_info(eng)  # expected keys: db, usr, host, port, url_masked (if available)

masked = dbg.get("url_masked") or _mask_url(os.environ.get("DB_URL", ""))
caption = f"DB debug → db={dbg.get('db')} user={dbg.get('usr')} host={dbg.get('host')}:{dbg.get('port')}"
if masked:
    caption += f" • DB_URL (masked): {masked}"
label = st.session_state.get("db_choice_label")
if label:
    caption += f" • Active target: {label}"
st.caption(caption)

# ---- Environment badge + Quick DB shortcuts --------------------------------
from sqlalchemy import text as _text  # reuse imported text if available

def _mask(u: str | None) -> str:
    if not u: return ""
    if "://" not in u: return u
    scheme, rest = u.split("://", 1)
    if "@" in rest and ":" in rest.split("@",1)[0]:
        user, hostpart = rest.split("@",1)[0], rest.split("@",1)[1]
        user = user.split(":",1)[0]
        return f"{scheme}://{user}:***@{hostpart}"
    return u

# probe the live connection for datadir / addr
try:
    with eng.begin() as _cx:
        _info = _cx.execute(_text("""
            select inet_server_addr()::text as addr,
                   inet_server_port()      as port,
                   current_setting('data_directory') as data_dir,
                   current_setting('listen_addresses') as listen
        """)).mappings().first()
except Exception:
    _info = {"addr":"", "port":"", "data_dir":"", "listen":""}

_db_url = os.environ.get("DB_URL","")
_masked_url = _mask(_db_url)

# classify environment
_env = "Unknown"
_color = "#999999"
if _info.get("data_dir","").startswith("/opt/homebrew/var/postgresql"):
    _env, _color = "LOCAL • Homebrew", "#16a34a"   # green
elif _info.get("data_dir","").startswith("/var/lib/postgresql"):
    _env, _color = "LOCAL • Docker", "#0ea5e9"     # sky
elif "pooler.supabase.com" in _db_url or "supabase.co" in _db_url:
    _env, _color = "SUPABASE • Cloud", "#f59e0b"   # amber

# banner
st.markdown(
    f"""
<div style="margin:8px 0;padding:10px 14px;border-radius:8px;background:{_color}22;border:1px solid {_color};">
  <strong style="color:{_color}">{_env}</strong>
  <span style="margin-left:10px;color:#555;">addr={_info.get('addr','?')}:{_info.get('port','?')}</span>
  <span style="margin-left:10px;color:#555;">data_dir={_info.get('data_dir','?')}</span>
  <span style="margin-left:10px;color:#555;">DB_URL={_mask(_db_url)}</span>
</div>
""",
    unsafe_allow_html=True,
)

# quick target buttons
c1, c2, c3 = st.columns([1,1,2])
LOCAL_URL   = "postgresql://postgres@127.0.0.1:5432/postgres?sslmode=disable"
DOCKER_URL  = "postgresql://postgres:postgres@127.0.0.1:54322/postgres?sslmode=disable"

with c1:
    if st.button("Use Homebrew 127.0.0.1:5432"):
        set_db_url(LOCAL_URL)
        st.session_state["db_choice_label"] = "LOCAL • Homebrew"
        st.rerun()

with c2:
    if st.button("Use Docker 127.0.0.1:54322"):
        set_db_url(DOCKER_URL)
        st.session_state["db_choice_label"] = "LOCAL • Docker"
        st.rerun()

with c3:
    sup = st.text_input("Supabase URL (pooler)", value=st.session_state.get("supabase_url",""), placeholder="postgresql://user:pass@host:port/db?sslmode=require")
    go_sup = st.button("Use Supabase URL")
    if go_sup and sup.strip():
        set_db_url(sup.strip())
        st.session_state["db_choice_label"] = "SUPABASE"
        st.session_state["supabase_url"] = sup.strip()
        st.rerun()


# Active connection probe (client + server addr + datadir)
with eng.begin() as cx:
    info = cx.execute(text("""
        select
          inet_client_addr()::text as client_addr,
          inet_server_addr()::text as server_addr,
          inet_server_port()      as port,
          current_database()      as db,
          session_user            as usr,
          current_setting('data_directory') as data_dir,
          current_setting('listen_addresses') as listen_addrs
    """)).mappings().first()

localish = {"127.0.0.1", "::1", None}  # None → unix socket

# also consider: app says host 127.0.0.1 / localhost, Postgres is listening on '*',
# or the data dir is a typical local path (docker/mac defaults)
host_hint = (dbg.get("host") in {"127.0.0.1", "localhost"})
raw_listen = str(info.get("listen_addrs") or "")
listen_set = {s.strip() for s in raw_listen.split(",")}
listen_hint = bool(listen_set & {"*", "localhost", "127.0.0.1"})
datadir_hint = str(info.get("data_dir") or "").startswith(("/var/lib/postgresql/data", "/usr/local/var/postgres"))

is_local = (
    info.get("server_addr") in localish
    or info.get("client_addr") in localish
    or host_hint
    or listen_hint
    or datadir_hint
)

badge = "✅" if is_local else "ℹ️"
st.caption(
    f"{badge} client={info['client_addr']} • server={info['server_addr']}:{info['port']} "
    f"db={info['db']} user={info['usr']} • data_dir={info['data_dir']} • listen={info['listen_addrs']}"
)

# -----------------------------------------------------------------------------
# Diagnostics controls
# -----------------------------------------------------------------------------
c1, c2 = st.columns([1, 1], vertical_alignment="center")
with c1:
    do_refresh = st.button("Refresh diagnostics", type="primary")
with c2:
    do_deep = st.toggle("Deep checks", value=False, help="Include view checks and empty-table scan")

# --- Danger zone: wipe current DB's public schema ---
with st.expander("Danger zone", expanded=False):
    st.write("This will delete **all data** in the `public` schema of the currently connected DB.")
    do_wipe = st.checkbox("I understand this is destructive.")
    if st.button("🧨 Wipe local DB", disabled=not do_wipe):
        with eng.begin() as cx:
            cx.execute(text("""
                DO $$
                DECLARE stmt text;
                BEGIN
                  SELECT 'TRUNCATE TABLE ' || string_agg(format('%I.%I', schemaname, tablename), ', ')
                         || ' RESTART IDENTITY CASCADE'
                    INTO stmt
                  FROM pg_tables
                  WHERE schemaname='public';
                  IF stmt IS NOT NULL THEN EXECUTE stmt; END IF;
                END$$;
            """))
        st.success("Local DB wiped. Re-import via **📤 New fish from CSV**.")
        st.rerun()

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def _counts(conn) -> pd.DataFrame:
    q = text("""
        with t(name, nrows) as (
          select 'fish',                             count(*) from public.fish
          union all select 'fish_transgene_alleles', count(*) from public.fish_transgene_alleles
          union all select 'transgene_alleles',      count(*) from public.transgene_alleles
          union all select 'transgene_allele_registry', count(*) from public.transgene_allele_registry
          union all select 'transgene_allele_counters', count(*) from public.transgene_allele_counters
        ),
        v(name, nrows) as (
          select 'v_fish_overview',                  count(*) from public.v_fish_overview
          union all select 'vw_fish_overview_with_label', count(*) from public.vw_fish_overview_with_label
        )
        select * from t
        union all
        select * from v
        order by name
    """)
    rows = conn.execute(q).mappings().all()
    return pd.DataFrame(rows)

def _empties(conn) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = conn.execute(text("""
        select table_schema, table_name
        from information_schema.tables
        where table_schema='public' and table_type='BASE TABLE'
        order by 1,2
    """)).mappings().all()

    data: List[Dict[str, Any]] = []
    for r in rows:
        tn = f"{r['table_schema']}.{r['table_name']}"
        try:
            n = conn.execute(text(f"select count(*) from {tn}")).scalar()
        except Exception as e:
            n = f"ERR: {e.__class__.__name__}"
        data.append({"table": tn, "rows": n})
    df = pd.DataFrame(data)
    if not df.empty:
        df = df.sort_values(["rows", "table"], ascending=[True, True])
    return df

# -----------------------------------------------------------------------------
# Run diagnostics
# -----------------------------------------------------------------------------
with eng.begin() as cxn:
    df_counts = _counts(cxn)

st.subheader("Row counts (tables & views)")
st.dataframe(df_counts, width='stretch')

if do_deep:
    with st.spinner("Scanning for empty tables…"):
        with eng.begin() as cxn:
            df_empty = _empties(cxn)
        st.subheader("Empty / small tables (public)")
        st.dataframe(
            df_empty[df_empty["rows"].apply(lambda x: isinstance(x, int) and x == 0)],
            width='stretch',
        )
        st.caption("Only showing completely empty user tables. Toggle off Deep checks to hide.")

# Minimal footer
st.markdown("---")
st.caption("Use the sidebar for pages. This home view focuses on DB selection and diagnostics.")