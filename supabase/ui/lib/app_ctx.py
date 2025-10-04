# supabase/ui/lib/app_ctx.py
from __future__ import annotations

# path shim so imports work no matter how Streamlit launches
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]  # .../carp_v2
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import os
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse

import streamlit as st
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

def _ensure_sslmode(url: str) -> str:
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

def _resolve_db_url() -> str:
    # Order of precedence: session-set → secrets/env → local default
    url = st.session_state.get("DB_URL") \
          or st.secrets.get("DB_URL", "") \
          or os.getenv("DATABASE_URL") \
          or os.getenv("DB_URL") \
          or "postgresql://postgres@localhost:5432/postgres?sslmode=disable"
    return _ensure_sslmode(url)

@st.cache_resource(show_spinner=False)
def _engine_for(url: str) -> Engine:
    if not url:
        raise RuntimeError("Empty DB URL")
    return create_engine(url, pool_pre_ping=True, future=True)

def get_engine() -> Engine:
    url = _resolve_db_url()
    return _engine_for(url)

def engine_info(eng: Engine | None = None) -> dict:
    eng = eng or get_engine()
    with eng.begin() as cx:
        row = cx.execute(text("""
            select current_database() as db,
                   inet_server_addr()::text as host,
                   inet_server_port()::int  as port,
                   current_user as usr
        """)).mappings().first()
    return dict(row)

def set_db_url(url: str) -> None:
    st.session_state["DB_URL"] = _ensure_sslmode(url)
    _engine_for.clear()  # next get_engine() recreates with new URL

def is_local_url(url: str) -> bool:
    u = urlparse(url)
    host = (u.hostname or "").lower() if u.hostname else ""
    return host in {"localhost", "127.0.0.1", "::1"}