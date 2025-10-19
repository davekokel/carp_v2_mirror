from __future__ import annotations

import os
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

_cached_engine: Engine | None = None
_cached_pw: str | None = None

def _maybe_rebuild_engine(url: str) -> Engine:
    global _cached_engine, _cached_url
    if not url:
        raise RuntimeError("DB_URL not set")
    if _cached_engine is not None and _cached_url == url:
        return _cached_engine
    _cached_engine = create_engine(url, pool_pre_ping=True, pool_recycle=1800)
    _cached_url = url
    return _cached_engine

def get_engine() -> Engine:
    return _maybe_rebuild_engine(os.getenv("DB_URL", ""))
