from __future__ import annotations
# supabase/ui/lib/db.py
import os
import hashlib
from urllib.parse import urlparse
import streamlit as st
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
# We allow a page to set its own DB URL (e.g., a LOCAL/STAGING chooser)
# Pages set this once via set_page_db_url(url); all other pages fall back to DB_URL env.
_PAGE_DB_ENV = "ACTIVE_DB_URL"
def set_page_db_url(url: str | None) -> None:
    """Record a page-scoped DB URL (stored in process env)."""
    if url:
        os.environ[_PAGE_DB_ENV] = url
def resolve_db_url() -> str:
    """Resolve the effective DB URL with sensible fallbacks."""
    return (
        os.environ.get(_PAGE_DB_ENV)
        or os.environ.get("DB_URL")
        or "postgresql://postgres:postgres@localhost:5432/carp_v2?sslmode=disable"
    )
def env_badge(url: str | None = None) -> tuple[str, str, str]:
    """Return (env_label, host, short_key) for display."""
    u = url or resolve_db_url()
    host = urlparse(u).hostname or ""
    env = "LOCAL" if host in {"localhost", "127.0.0.1", "::1"} else "STAGING"
    key = hashlib.md5(u.encode()).hexdigest()[:8]
    return env, host, key
@st.cache_resource(show_spinner=False)
def _engine_for_url(url: str) -> Engine:
    return create_engine(url)
def get_engine() -> Engine:
    """Get a cached SQLAlchemy engine for the current resolved URL."""
    return _engine_for_url(resolve_db_url())
def show_env_badge(url: str | None = None) -> None:
    """Convenience: render the Env/Host/Key caption in the page."""
    env, host, key = env_badge(url)
    st.caption(f"Env: {env} • Host: {host} • Key: `{key}`")