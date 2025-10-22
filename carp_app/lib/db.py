from __future__ import annotations
from sqlalchemy.engine import Engine
from carp_app.ui.lib.app_ctx import get_engine as _shared_get_engine

__all__ = ["get_engine"]

def get_engine() -> Engine:
    return _shared_get_engine()
