# supabase/ui/lib/db.py
from __future__ import annotations

import os
from typing import Optional, Union, Mapping, Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, Connection
from urllib.parse import quote_plus

# optional psycopg3 import for raw connection use
try:
    import psycopg  # psycopg v3
except Exception:
    psycopg = None  # imported lazily in get_conn()

# ---------- secrets helpers ----------

def _get_secret(name: str, default: Optional[str] = None) -> Optional[str]:
    """Read a value from Streamlit secrets if available; else env vars."""
    try:
        import streamlit as st  # type: ignore
        return st.secrets.get(name, default)
    except Exception:
        return os.getenv(name, default)

# ---------- DSN builders ----------

def _dsn_for_sqlalchemy() -> Optional[str]:
    """
    Build a SQLAlchemy URL.
    Prefers CONN/CONN_*; else builds postgresql+psycopg:// from PG* parts.
    """
    for key in ("CONN", "CONN_POOL", "CONN_DIRECT", "CONN_STAGING", "CONN_LOCAL"):
        dsn = _get_secret(key)
        if dsn and str(dsn).strip():
            return str(dsn).strip()

    host = _get_secret("PGHOST")
    user = _get_secret("PGUSER")
    pwd  = _get_secret("PGPASSWORD")
    db   = _get_secret("PGDATABASE", "postgres")
    port = str(_get_secret("PGPORT", "5432"))
    ssl  = _get_secret("SSL_MODE", "require")

    if host and user and pwd:
        return f"postgresql+psycopg://{user}:{pwd}@{host}:{port}/{db}?sslmode={ssl}"
    return None

def _dsn_for_psycopg() -> Optional[str]:
    """
    Build a DSN suitable for psycopg.connect().
    Prefers postgres:// / postgresql:// if provided, else builds from PG*.
    """
    for key in ("CONN", "CONN_POOL", "CONN_DIRECT", "CONN_STAGING", "CONN_LOCAL"):
        dsn = _get_secret(key)
        if dsn and str(dsn).strip():
            dsn = str(dsn).strip()
            if dsn.startswith(("postgres://", "postgresql://")):
                return dsn

    host = _get_secret("PGHOST")
    user = _get_secret("PGUSER")
    pwd  = _get_secret("PGPASSWORD")
    db   = _get_secret("PGDATABASE", "postgres")
    port = str(_get_secret("PGPORT", "5432"))
    ssl  = _get_secret("SSL_MODE", "require")

    if host and user and pwd:
        return f"postgres://{user}:{pwd}@{host}:{port}/{db}?sslmode={ssl}"
    return None

# ---------- Engine factory (SQLAlchemy) ----------

def get_engine(dsn: Optional[str] = None) -> Engine:
    """
    Build a SQLAlchemy Engine.

    Preference order:
      1) explicit DSN arg
      2) DSN from secrets (CONN/CONN_POOL/etc.)
      3) PG* parts
    """
    url = dsn or _dsn_for_sqlalchemy()
    if not url:
        raise KeyError(
            "Database config missing. Provide CONN/CONN_* or PG* secrets/env."
        )

    # PGBouncer-friendly; harmless for direct connections
    return create_engine(
        url,
        pool_pre_ping=True,
        future=True,
        connect_args={"prepare_threshold": None},
    )

# ---------- Convenience helpers (SQLAlchemy) ----------

def quick_db_check(engine: Engine) -> str:
    try:
        with engine.connect() as cx:
            v = cx.execute(text("select version()")).scalar() or ""
            who = cx.execute(text("select current_user")).scalar()
            return f"OK: {who} @ {str(v).split()[0]}"
    except Exception as e:
        return f"DB check failed: {e}"

def fetch_df(conn: Union[Engine, Connection], sql: str, params: Optional[Mapping[str, Any]] = None):
    """Read a SELECT into a pandas DataFrame."""
    import pandas as pd
    return pd.read_sql(text(sql), conn, params=params or {})

def exec_sql(conn: Union[Engine, Connection], sql: str, params: Optional[Mapping[str, Any]] = None):
    """Execute arbitrary SQL (Engine or Connection)."""
    if isinstance(conn, Engine):
        with conn.begin() as cx:
            cx.execute(text(sql), params or {})
    else:
        conn.execute(text(sql), params or {})

# ---------- Raw psycopg3 connection for Streamlit pages ----------

def get_conn():
    """
    Return a psycopg3 connection (autocommit ON).
    Matches pages that import: `from lib.db import get_conn`.
    """
    if psycopg is None:
        raise ImportError("psycopg is not installed; install psycopg[binary]>=3.2")
    dsn = _dsn_for_psycopg()
    if not dsn:
        raise KeyError("No postgres DSN for psycopg. Ensure CONN or PG* secrets are set.")
    cx = psycopg.connect(dsn)
    cx.autocommit = True
    return cx



def _dsn_from_secrets() -> Optional[str]:
    """
    Build a DSN string from secrets/env.
    Preference order:
      1) Direct DSN keys (CONN, CONN_POOL, CONN_DIRECT, CONN_STAGING, CONN_LOCAL)
      2) PG* parts (PGHOST/PGPORT/PGUSER/PGPASSWORD/PGDATABASE) + SSL_MODE
    """
    for key in ("CONN", "CONN_POOL", "CONN_DIRECT", "CONN_STAGING", "CONN_LOCAL"):
        dsn = _get_secret(key)
        if dsn and str(dsn).strip():
            return str(dsn).strip()

    host = _get_secret("PGHOST")
    user = _get_secret("PGUSER")
    pwd  = _get_secret("PGPASSWORD")
    db   = _get_secret("PGDATABASE", "postgres")
    port = str(_get_secret("PGPORT", "5432"))
    ssl  = (_get_secret("SSL_MODE", "require") or "require").strip()

    if host and user and pwd:
        return f"postgresql+psycopg://{user}:{quote_plus(str(pwd))}@{host}:{port}/{db}?sslmode={ssl}"
    return None

    host = _get_secret("PGHOST")
    user = _get_secret("PGUSER")
    pwd  = _get_secret("PGPASSWORD")
    db   = _get_secret("PGDATABASE", "postgres")
    port = str(_get_secret("PGPORT", "5432"))
    ssl  = (_get_secret("SSL_MODE", "require") or "require").strip()

    if host and user and pwd:
        return f"postgresql+psycopg://{user}:{quote_plus(str(pwd))}@{host}:{port}/{db}?sslmode={ssl}"
    return None
