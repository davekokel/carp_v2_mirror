from __future__ import annotations
from sqlalchemy import create_engine
from carp_app.lib.secret import db_url
_ENGINE = None
def get_engine():
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = create_engine(db_url(), pool_pre_ping=True, future=True)
    return _ENGINE
