# supabase/ui/lib/app_ctx.py  — full replacement
from __future__ import annotations

import os
from typing import Dict, Optional, Tuple

import streamlit as st
APP_TZ = os.getenv('APP_TZ', 'America/Los_Angeles')
from sqlalchemy import create_engine, text, event
from sqlalchemy.engine import Engine

# ----------------------------------------------------------------------
# Module-level cache: a single engine shared by all pages in a run
# ----------------------------------------------------------------------
_cached_url: Optional[str] = None
_cached_engine: Optional[Engine] = None


# ----------------------------------------------------------------------
# Internals
# ----------------------------------------------------------------------
def _attach_tz_listener(engine):
    """Attach a one-time 'connect' listener to set the session time zone."""
    # Prevent multiple attachments in a long-lived process.
    if getattr(engine, "_tz_attached", False):
        return engine

    @event.listens_for(engine, "connect")
    def _set_tz(dbapi_conn, _):
        # Runs at the DB-API connection level (fast, reliable)
        try:
            cur = dbapi_conn.cursor()
            cur.execute("SET TIME ZONE %s", (APP_TZ,))
            cur.close()
        except Exception:
            # Don't break the app if TZ can't be set — just continue
            pass

    engine._tz_attached = True
    return engine

def _mask(url: Optional[str]) -> str:
    """Mask password in a DB URL for safe display."""
    if not url or "://" not in url:
        return url or ""
    scheme, rest = url.split("://", 1)
    if "@" in rest and ":" in rest.split("@", 1)[0]:
        creds, hostpart = rest.split("@", 1)
        user = creds.split(":", 1)[0]
        return f"{scheme}://{user}:***@{hostpart}"
    return url


def _default_local_url() -> str:
    """Hard default: Homebrew Postgres on localhost:5432."""
    return "postgresql://postgres@127.0.0.1:5432/postgres?sslmode=disable"


def _normalize_url(url: Optional[str]) -> str:
    """Return a trimmed, non-empty URL (or default local)."""
    val = (url or "").strip()
    return val if val else _default_local_url()


def _resolve_db_url() -> str:
    """
    Single point of truth for the active DB URL.
    Order of precedence:
      1) st.session_state["DB_URL"] (set by Diagnostics buttons)
      2) os.environ["DB_URL"]
      3) APP_FORCE_LOCAL -> default local
      4) default local
    """
    url = st.session_state.get("DB_URL")
    if url:
        return _normalize_url(url)

    url = os.environ.get("DB_URL")
    if url:
        url = _normalize_url(url)
        st.session_state["DB_URL"] = url
        return url

    if os.environ.get("APP_FORCE_LOCAL"):
        url = _default_local_url()
        st.session_state["DB_URL"] = url
        return url

    url = _default_local_url()
    st.session_state["DB_URL"] = url
    return url


def _maybe_rebuild_engine(url: str) -> Engine:
    """Create/reuse a SQLAlchemy engine for the given URL."""
    global _cached_engine, _cached_url
    if _cached_engine is None or _cached_url != url:
        # pre_ping=True avoids stale connections on resume; future=True for SQLA 2.0 style
        _cached_engine = create_engine(url, pool_pre_ping=True, future=True)
        _cached_engine = _attach_tz_listener(_cached_engine)
        _cached_url = url
    return _cached_engine


# ----------------------------------------------------------------------
# Public API
# ----------------------------------------------------------------------
def set_db_url(url: str) -> None:
    """
    Set and persist the DB URL for all pages in this app session.
    This also invalidates the cached engine so the next get_engine() reconnects.
    """
    global _cached_engine, _cached_url
    url = _normalize_url(url)
    st.session_state["DB_URL"] = url
    os.environ["DB_URL"] = url
    if _cached_url != url:
        _cached_engine = None
        _cached_url = None


def clear_engine_cache() -> None:
    """Explicitly drop the cached engine (forces reconnect on next get_engine())."""
    global _cached_engine, _cached_url
    _cached_engine = None
    _cached_url = None


def get_engine() -> Engine:
    """Return a shared SQLAlchemy engine bound to the current DB URL."""
    url = _resolve_db_url()
    return _maybe_rebuild_engine(url)


def engine_info(eng: Optional[Engine] = None) -> Dict[str, str]:
    """
    Lightweight diagnostics for headers/badges and debug captions.
    Returns: {url_masked, db, usr, host, port}
    """
    if eng is None:
        eng = get_engine()

    url = st.session_state.get("DB_URL", os.environ.get("DB_URL", _default_local_url()))
    info: Dict[str, str] = {
        "url_masked": _mask(url),
        "db": "",
        "usr": "",
        "host": "",
        "port": "",
    }

    # Parse basics from the SQLAlchemy URL when available
    try:
        u = eng.url  # type: ignore[attr-defined]
        info["usr"] = getattr(u, "username", "") or ""
        info["host"] = getattr(u, "host", "") or ""
        info["port"] = str(getattr(u, "port", "") or "")
        info["db"] = getattr(u, "database", "") or ""
    except Exception:
        pass

    # Live probe (best-effort; ignore failures)
    try:
        with eng.begin() as cx:
            row = cx.execute(
                text(
                    """
                    select current_database() as db,
                           inet_server_addr()::text as addr,
                           inet_server_port()      as port
                    """
                )
            ).mappings().first()
        if row:
            info["db"] = info["db"] or row.get("db", "")
            # If URL didn't include host/port, prefer server addr/port
            if not info["host"]:
                info["host"] = row.get("addr", "") or ""
            if not info["port"]:
                info["port"] = str(row.get("port", "") or "")
    except Exception:
        pass

    return info

from sqlalchemy import text as _t
def stamp_app_user(eng, user: str):
    if user:
        with eng.begin() as cx:
            cx.execute(_t("select set_config('app.user', :u, true)"), {"u": user})