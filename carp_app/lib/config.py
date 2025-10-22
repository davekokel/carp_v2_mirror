# carp_app/lib/config.py
from __future__ import annotations
import os
from functools import lru_cache

def _from_env() -> str | None:
    return os.getenv("DB_URL") or os.getenv("DATABASE_URL")

def _from_streamlit() -> str | None:
    try:
        import streamlit as st  # available in app runtime
        return st.secrets.get("DB_URL") or st.secrets.get("database_url")
    except Exception:
        return None

@lru_cache
def resolve_db_url() -> str:
    v = _from_env() or _from_streamlit()
    if not v:
        raise RuntimeError(
            "DB_URL not set. Set it in your shell (export DB_URL=...) "
            "or add DB_URL to .streamlit/secrets.toml."
        )
    return v

DB_URL: str = resolve_db_url()