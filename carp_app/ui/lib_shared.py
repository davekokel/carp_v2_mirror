from __future__ import annotations
# supabase/ui/lib_shared.py

import os
from typing import Optional, Tuple, Dict, Any, List
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse

import streamlit as st
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

# =========================
# Secrets & DSN resolution
# =========================

def _get_secret(key: str, default: Optional[str] = None) -> Optional[str]:
    """Read from Streamlit secrets; fall back to env var."""
    try:
        val = st.secrets.get(key)  # type: ignore[attr-defined]
        if val is None or (isinstance(val, str) and val.strip() == ""):
            raise KeyError
        return str(val)
    except Exception:
        v = os.getenv(key)
        return v if (v and v.strip()) else default


def _first_nonempty(*vals: Optional[str]) -> Optional[str]:
    for v in vals:
        if v and str(v).strip():
            return str(v).strip()
    return None


def _build_dsn_from_pg_parts() -> Optional[str]:
    """
    Build a SQLAlchemy DSN from PG* pieces in secrets/env. Return None if incomplete.
    Uses psycopg (v3) driver string.
    """
    host = _get_secret("PGHOST")
    user = _get_secret("PGUSER")
    pwd  = _get_secret("PGPASSWORD")
    db   = _get_secret("PGDATABASE", "postgres")
    port = _get_secret("PGPORT", "5432")

    if not (host and user and pwd):
        return None

    # Always require SSL for Supabase / cloud connections
    return f"postgresql+psycopg://{user}:{pwd}@{host}:{port}/{db}?sslmode=require"


def pick_environment() -> Tuple[str, Optional[str]]:
    """
    Decide which environment is active and return (env_name, dsn_or_none).

    Priority for DSN:
      - ENV_NAME == "staging": CONN_STAGING -> CONN -> build from PG*
      - ENV_NAME == "local":   CONN_LOCAL   -> CONN -> build from PG*
      - Otherwise:             CONN         -> build from PG*
    """
    env_name = _get_secret("ENV_NAME", os.getenv("ENV_NAME", "staging")).lower()

    dsn: Optional[str] = None
    if env_name == "staging":
        dsn = _first_nonempty(
            _get_secret("CONN_STAGING"),
            _get_secret("CONN"),
            _build_dsn_from_pg_parts(),
        )
    elif env_name == "local":
        dsn = _first_nonempty(
            _get_secret("CONN_LOCAL"),
            _get_secret("CONN"),
            _build_dsn_from_pg_parts(),
        )
    else:
        dsn = _first_nonempty(
            _get_secret("CONN"),
            _build_dsn_from_pg_parts(),
        )

    return env_name, dsn


# =========================
# Shared query utilities
# =========================

def parse_query(raw: Optional[str] = None) -> Dict[str, Any]:
    """
    Parse compact query text.
    Tokens (case-insensitive):
      - batch:<value>
      - search:<value with spaces ok via quotes or underscores>
      - limit:<n>
      - mode:and|or   (alias: mode:any -> OR)
    Free tokens (no k:v) are treated as search terms.
    Returns a dict with keys: batch, search, terms, limit, mode.
    """
    result: Dict[str, Any] = {
        "batch": None,
        "search": None,
        "terms": [],
        "limit": None,
        "mode": "AND",
    }
    if not raw:
        return result

    s = str(raw).strip()
    if not s:
        return result

    tokens = s.split()
    terms: List[str] = []

    for t in tokens:
        if ":" in t:
            k, v = t.split(":", 1)
            k = k.lower().strip()
            v = v.strip().strip('"').strip("'")
            if k == "batch" and v:
                result["batch"] = v
                continue
            if k == "search" and v:
                terms.append(v)
                continue
            if k == "limit" and v.isdigit():
                result["limit"] = int(v)
                continue
            if k == "mode" and v:
                mv = v.upper()
                result["mode"] = "OR" if mv in ("OR", "ANY") else "AND"
                continue
        if t.strip():
            terms.append(t.strip())

    result["terms"] = terms
    result["search"] = " ".join(terms) if terms else None
    return result


# =========================
# Centralized DB bootstrap
# =========================

def _ensure_sslmode(url: str) -> str:
    """Ensure sensible sslmode based on host."""
    if not url:
        return url
    u = urlparse(url)
    host = (u.hostname or "").lower() if u.hostname else ""
    q = dict(parse_qsl(u.query, keep_blank_values=True))
    if host in {"localhost", "127.0.0.1", "::1"}:
        q["sslmode"] = "disable"
    else:
        q.setdefault("sslmode", "require")
    return urlunparse((u.scheme, u.netloc, u.path, u.params, urlencode(q), u.fragment))


def _mask_db_url(u: str) -> str:
    try:
        p = urlparse(u or "")
        if "@" in p.netloc:
            user, host = p.netloc.split("@", 1)
            user = user.split(":", 1)[0]
            netloc = f"{user}:***@{host}"
        else:
            netloc = p.netloc
        return p._replace(netloc=netloc).geturl()
    except Exception:
        return "(unavailable)"


@st.cache_resource(show_spinner=False)
def _engine_for(db_url: str) -> Engine:
    """Create (or return cached) Engine keyed by db_url."""
    assert db_url, "DB URL must be provided"
    return create_engine(_ensure_sslmode(db_url), pool_pre_ping=True, future=True)


def db_picker(show_ui: bool = False) -> Tuple[Engine, str]:
    """
    Initialize one DB URL + Engine for the whole app (stored in st.session_state).
    If show_ui=True (e.g., on the Home page), render a selector to switch DBs.
    Returns (engine, effective_db_url).
    """
    if "DB_URL" not in st.session_state:
        env_url = os.environ.get("DB_URL") or os.environ.get("DATABASE_URL")
        if not env_url:
            _, env_url = pick_environment()
        st.session_state.DB_URL = env_url or "postgresql://postgres@localhost:5432/postgres?sslmode=disable"

    db_url = st.session_state.DB_URL

    if show_ui:
        st.subheader("Database connection")
        env_default = os.environ.get("DB_URL") or os.environ.get("DATABASE_URL") or db_url
        local_default = "postgresql://postgres@localhost:5432/postgres?sslmode=disable"

        choice = st.radio("Choose DB target", ["Local (localhost)", "Env/Default", "Custom"], horizontal=True)
        custom = st.text_input("Custom DB URL", value=db_url if choice == "Custom" else "",
                               placeholder="postgresql://user:pass@host:port/db?sslmode=...")

        db_url = (
            local_default if choice == "Local (localhost)" else
            env_default   if choice == "Env/Default"     else
            (custom.strip() or env_default)
        )

        colA, colB = st.columns([1, 1])
        with colA:
            if st.button("Connect to selected DB"):
                st.session_state.DB_URL = db_url
                _engine_for.clear()  # clear cache for new URL
                st.success("Reconnected to database.")
                st.rerun()
        with colB:
            st.caption(f"DB_URL (masked): {_mask_db_url(db_url)}")
    else:
        st.caption(f"DB_URL (masked): {_mask_db_url(db_url)}")

    eng = _engine_for(db_url)
    return eng, db_url


def current_engine() -> Engine:
    """
    Convenience accessor for pages that already called db_picker on Home.
    Falls back to env → pick_environment → localhost.
    """
    db_url = st.session_state.get("DB_URL") \
             or os.environ.get("DB_URL") or os.environ.get("DATABASE_URL")
    if not db_url:
        _, db_url = pick_environment()
    if not db_url:
        db_url = "postgresql://postgres@localhost:5432/postgres?sslmode=disable"
        st.session_state.DB_URL = db_url
    return _engine_for(db_url)


# =========================
# Optional: enforce policy
# =========================

def ensure_unique_fish_code_only(eng: Engine) -> None:
    """
    Drop any UNIQUE(name) on public.fish (constraints **and** unique indexes, incl. LOWER(name)),
    and ensure UNIQUE(fish_code). Safe to call at page start in write flows.
    """
    with eng.begin() as conn:
        # Drop UNIQUE constraints on name
        conn.execute(text("""
            do $$
            declare r record;
            begin
              for r in
                select c.conname
                from pg_constraint c
                join pg_class t on t.oid = c.conrelid
                join pg_namespace n on n.oid = t.relnamespace
                where n.nspname='public' and t.relname='fish' and c.contype='u'
                  and pg_get_constraintdef(c.oid) ilike 'UNIQUE (name%'
              loop
                execute format('alter table public.fish drop constraint %I', r.conname);
              end loop;
            end$$;
        """))
        # Drop UNIQUE indexes on name (plain or LOWER(name) variants)
        conn.execute(text("""
            do $$
            declare r record;
            begin
              for r in
                select indexname, indexdef
                from pg_indexes
                where schemaname='public'
                  and tablename='fish'
                  and (
                    indexdef ilike 'create unique index%on public.fish% (name%'
                    or indexdef ilike 'create unique index%on public.fish%(lower(name%'
                    or indexdef ilike 'create unique index%on public.fish%(lower((btrim((name)::text)))%'
                  )
              loop
                execute format('drop index if exists public.%I', r.indexname);
              end loop;
            end$$;
        """))
        # Ensure fish_code is the only unique identity
        conn.execute(text("create unique index if not exists uq_fish_code on public.fish(fish_code)"))
        # Optional: non-unique index on name (only if the column exists)
        conn.execute(text("""
            do $$
            begin
              if exists (
                select 1 from information_schema.columns
                where table_schema='public' and table_name='fish' and column_name='name'
              ) then
                create index if not exists ix_fish_name on public.fish(name);
              end if;
            end$$;
        """))


# =========================
# Tiny debug helper
# =========================

def connection_info(eng: Engine) -> Dict[str, str]:
    with eng.begin() as conn:
        row = conn.execute(text("select current_database() db, current_user usr")).mappings().first()
    return {"db": row["db"], "user": row["usr"]}