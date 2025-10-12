from __future__ import annotations

# --- boot router (runs before importing streamlit) ---
import os, sys, runpy
from pathlib import Path

_boot = os.getenv("APP_BOOT", "").lower()
if _boot in {"ping", "diagnostics"}:
    ROOT = Path(__file__).resolve().parent  # .../supabase/ui
    target = {
        "ping":        ROOT / "pages" / "001_db_ping_min.py",
        "diagnostics": ROOT / "pages" / "001_🧪_diagnostics_clean.py",
    }[_boot]
    runpy.run_path(str(target), run_name="__main__")
    sys.exit(0)

# now import the rest of your app
import os, sys, time
from pathlib import Path
import streamlit as st
import pandas as pd
import subprocess
from sqlalchemy import text
def _build_meta():
    """
    Try to read the current git commit (short SHA), commit time, and branch from the checkout.
    Fallback to env/secrets if git metadata isn't present.
    """
    try:
        root = Path(__file__).resolve().parents[2]  # repo root
        sha = subprocess.check_output(["git","rev-parse","--short","HEAD"], cwd=root, text=True).strip()
        ts  = subprocess.check_output(["git","show","-s","--format=%ci","HEAD"], cwd=root, text=True).strip()
        br  = subprocess.check_output(["git","rev-parse","--abbrev-ref","HEAD"], cwd=root, text=True).strip()
        # In some deploys it's a detached HEAD; show env APP_ENV instead
        if br == "HEAD":
            br = os.getenv("APP_ENV","").lower() or "detached"
        return sha, ts, br
    except Exception:
        # fallbacks (Secrets or env)
        sha = (getattr(st, "secrets", {}).get("BUILD_SHA") if hasattr(st,"secrets") else None) or os.getenv("BUILD_SHA","")
        ts  = (getattr(st, "secrets", {}).get("BUILD_TIME") if hasattr(st,"secrets") else None) or os.getenv("BUILD_TIME","")
        br  = (getattr(st, "secrets", {}).get("BUILD_BRANCH") if hasattr(st,"secrets") else None) or os.getenv("BUILD_BRANCH","") or os.getenv("APP_ENV","").lower()
        return sha, ts, br

# ...keep the rest of your file exactly as you had it (ENV badge, imports, etc.) ...

# --- Robust import path so this works locally and in cloud runners ---
ROOT = Path(__file__).resolve().parents[2]  # …/carp_v2
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
from supabase.ui.lib.prod_banner import show_prod_banner
show_prod_banner()
_sha,_ts,_br = _build_meta() or (getattr(st, "secrets", {}).get("BUILD_SHA") if hasattr(st, "secrets") else "")
if _sha:
    st.caption(f"BUILD: {_br or 'unknown'}@{_sha[:7]}{f' ({_ts})' if _ts else ''}")

if os.getenv("APP_ENV","local").lower() != "local" and not st.session_state.get("_db_bootstrapped"):
    import supabase.ui.lib.app_ctx as app_ctx
    # ensure no stale session URL can override env
    st.session_state.pop("DB_URL", None)
    st.session_state["db_choice"] = "env"
    st.session_state["db_custom"] = ""
    st.session_state["db_choice_label"] = "ENV/DEFAULT"
    app_ctx.clear_engine_cache()
    st.session_state["_db_bootstrapped"] = True
    st.rerun()

# Auto-bootstrap for non-local environments:
# ensure session DB_URL cannot override the process environment,
# clear engine cache, and rerun once.
if os.getenv("APP_ENV","local").lower() != "local" and not st.session_state.get("_db_bootstrapped"):
    import supabase.ui.lib.app_ctx as app_ctx
    st.session_state.pop("DB_URL", None)       # remove any stale 127.0.0.1 URL
    st.session_state["db_choice"] = "env"
    st.session_state["db_custom"] = ""
    st.session_state["db_choice_label"] = "ENV/DEFAULT"
    app_ctx.clear_engine_cache()
    st.session_state["_db_bootstrapped"] = True
    st.rerun()

# ---------------------------------------------------------------------
# Quick engine reset button
# ---------------------------------------------------------------------
import supabase.ui.lib.app_ctx as app_ctx

st.divider()
if st.button("🔁 Reconnect DB Engine", type="primary", use_container_width=True):
    app_ctx.clear_engine_cache()
    st.success("Engine cache cleared — reconnecting using current DB_URL …")
    st.rerun()
st.divider()

# --- One-click: force Env/Default, clear session URL, rebuild engine
c0a, c0b = st.columns([1,2])
with c0a:
    if st.button("Use Env (Supabase) now", use_container_width=True):
        import supabase.ui.lib.app_ctx as app_ctx
        st.session_state.pop("DB_URL", None)   # remove stale session override
        st.session_state["db_choice"] = "env"
        st.session_state["db_custom"] = ""
        st.session_state["db_choice_label"] = "ENV/DEFAULT"
        app_ctx.clear_engine_cache()
        st.rerun()

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
    import supabase.ui.lib.app_ctx as app_ctx

    st.session_state["db_choice"] = choice

    if choice == "local":
        url = DEFAULT_LOCAL
        os.environ["DB_URL"] = url
        st.session_state["db_custom"] = url
        st.session_state["db_choice_label"] = "LOCAL • Homebrew"

    elif choice == "custom":
        url = (custom_url or "").strip()
        if not url:
            st.warning("Enter a custom DB URL to connect.")
            st.stop()
        os.environ["DB_URL"] = url
        st.session_state["db_custom"] = url
        st.session_state["db_choice_label"] = "CUSTOM"

    else:  # env/default
        st.session_state.pop("DB_URL", None)         # clear stale session URL
        st.session_state["db_custom"] = ""
        st.session_state["db_choice_label"] = "ENV/DEFAULT"

    app_ctx.clear_engine_cache()                     # force reconnect
    st.rerun()

# -----------------------------------------------------------------------------
# DB connection + header diagnostic line
# -----------------------------------------------------------------------------
try:
    eng = get_engine()
    dbg = engine_info(eng)
except Exception as e:
    st.error(f"DB connect failed: {e}")
    st.stop()  # expected keys: db, usr, host, port, url_masked (if available)

from supabase.ui.lib.app_ctx import stamp_app_user
who = getattr(st.experimental_user, "email", "") if hasattr(st, "experimental_user") else ""
stamp_app_user(eng, who)

masked = dbg.get("url_masked") or _mask_url(os.environ.get("DB_URL", ""))
caption = f"DB debug → db={dbg.get('db')} user={dbg.get('usr')} host={dbg.get('host')}:{dbg.get('port')}"
if masked:
    caption += f" • DB_URL (masked): {masked}"
label = st.session_state.get("db_choice_label")
if label:
    caption += f" • Active target: {label}"
st.caption(caption)

# ---- Environment badge + Quick DB shortcuts --------------------------------
from sqlalchemy import text
def _build_meta():
    """
    Try to read the current git commit (short SHA), commit time, and branch from the checkout.
    Fallback to env/secrets if git metadata isn't present.
    """
    try:
        root = Path(__file__).resolve().parents[2]  # repo root
        sha = subprocess.check_output(["git","rev-parse","--short","HEAD"], cwd=root, text=True).strip()
        ts  = subprocess.check_output(["git","show","-s","--format=%ci","HEAD"], cwd=root, text=True).strip()
        br  = subprocess.check_output(["git","rev-parse","--abbrev-ref","HEAD"], cwd=root, text=True).strip()
        # In some deploys it's a detached HEAD; show env APP_ENV instead
        if br == "HEAD":
            br = os.getenv("APP_ENV","").lower() or "detached"
        return sha, ts, br
    except Exception:
        # fallbacks (Secrets or env)
        sha = (getattr(st, "secrets", {}).get("BUILD_SHA") if hasattr(st,"secrets") else None) or os.getenv("BUILD_SHA","")
        ts  = (getattr(st, "secrets", {}).get("BUILD_TIME") if hasattr(st,"secrets") else None) or os.getenv("BUILD_TIME","")
        br  = (getattr(st, "secrets", {}).get("BUILD_BRANCH") if hasattr(st,"secrets") else None) or os.getenv("BUILD_BRANCH","") or os.getenv("APP_ENV","").lower()
        return sha, ts, br

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
_supabase = ("pooler.supabase.com" in _db_url) or ("supabase.co" in _db_url) or os.getenv("PGHOST","").endswith(".supabase.co")
if _supabase:
    _env, _color = "SUPABASE • Cloud", "#f59e0b"
elif _info.get("data_dir","").startswith("/opt/homebrew/var/postgresql"):
    _env, _color = "LOCAL • Homebrew", "#16a34a"
elif (dbg.get("host") in {"127.0.0.1","localhost"} or str(_info.get("addr")) in {"127.0.0.1","::1","None"} or _info.get("data_dir","").startswith("/var/lib/postgresql")):
    _env, _color = "LOCAL • Docker", "#0ea5e9"
else:
    _env, _color = "REMOTE • Postgres", "#8b5cf6"
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
info = {"client_addr":"", "server_addr":"", "port":"", "db":"", "usr":"", "data_dir":"", "listen_addrs":""}
try:
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
        """)).mappings().first() or info
except Exception as e:
    st.warning(f"Live probe skipped: {e}")

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

# ---------------------------------------------------------------------
# Danger zone
# ---------------------------------------------------------------------
with st.expander("⚠️ Danger zone"):
    APP_ENV = os.getenv("APP_ENV", "local").lower()
    if APP_ENV != "local":
        st.info("Danger zone is disabled outside LOCAL.")
    else:
        st.write("Wipe all data in `public` schema (local only).")
        ok = st.checkbox("I understand this is destructive.")
        if st.button("🧨 Wipe local DB", disabled=not ok):
            try:
                # Hard runtime guard: only proceed if server is local
                with eng.begin() as cx:
                    is_local = cx.execute(text("""
                        select case
                                 when inet_server_addr()::text in ('127.0.0.1','::1') then true
                                 when current_setting('data_directory', true) like '/opt/homebrew/var/postgresql%' then true
                                 when current_setting('data_directory', true) like '/var/lib/postgresql/%' then true
                                 else false
                               end
                    """)).scalar()
                    if not is_local:
                        raise RuntimeError("Refusing to wipe: current DB is not local.")
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
                st.success("Local DB wiped.")
            except Exception as e:
                st.error(f"Wipe failed or blocked: {e}")

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
import time

def _try_counts_with_retry(eng, attempts: int = 3, sleep_s: float = 0.8):
    last_err = None
    for i in range(attempts):
        try:
            with eng.begin() as cxn:
                return _counts(cxn)
        except Exception as e:
            last_err = e
            time.sleep(sleep_s)
    raise last_err

st.subheader("Row counts (tables & views)")
if do_refresh:
    try:
        df_counts = _try_counts_with_retry(eng, attempts=3, sleep_s=0.8)
        st.dataframe(df_counts, width='stretch')
    except Exception as e:
        st.error(f"DB connect failed: {e}")
        st.info("Tips: click **🔁 Reconnect DB Engine**, then press **Refresh diagnostics** again.")
else:
    st.caption("Click **Refresh diagnostics** to probe the current DB.")

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