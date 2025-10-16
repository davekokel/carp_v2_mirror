from __future__ import annotations
import os, time, urllib.parse as _u
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from carp_app.lib.secret import db_url

_ENGINE = None

def _tweak_url(url: str) -> str:
    # ensure sslmode=require and channel_binding=disable on pooler URLs
    parts = _u.urlsplit(url)
    query = dict(_u.parse_qsl(parts.query, keep_blank_values=True))
    query.setdefault("sslmode", "require")
    # Some libpq builds + pooler can throw "duplicate SASL authentication request"
    query.setdefault("channel_binding", "disable")
    new_q = _u.urlencode(query)
    return _u.urlunsplit((parts.scheme, parts.netloc, parts.path, new_q, parts.fragment))

def _mk_engine(url: str):
    connect_args = {
        "connect_timeout": 10,
        "keepalives": 1,
        "keepalives_idle": 30,
        "keepalives_interval": 10,
        "keepalives_count": 5,
    }
    return create_engine(url, pool_pre_ping=True, future=True, connect_args=connect_args, pool_recycle=1800)

def get_engine():
    global _ENGINE
    if _ENGINE is not None:
        return _ENGINE
    url = _tweak_url(db_url())
    # optional bypass of pooler if you ever need it:
    if os.getenv("SUPABASE_USE_DIRECT", "") == "1":
        # replace pooler host/port with direct db host/port
        from carp_app.lib.config import STAGING_PROJECT_ID, PROD_PROJECT_ID
        proj = STAGING_PROJECT_ID or PROD_PROJECT_ID or ""
        if proj:
            url = url.replace("aws-1-us-west-1.pooler.supabase.com:6543", f"db.{proj}.supabase.co:5432")
            url = url.replace("aws-1-us-west-1.pooler.supabase.com", f"db.{proj}.supabase.co")
            url = url.replace(":6543", ":5432")
        url = _tweak_url(url)
    last = None
    for _ in range(3):
        try:
            _ENGINE = _mk_engine(url)
            with _ENGINE.connect() as cx:
                cx.exec_driver_sql("select 1")
            return _ENGINE
        except OperationalError as e:
            last = e
            time.sleep(1)
    raise last
