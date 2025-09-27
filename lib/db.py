# supabase/ui/lib/db.py
from __future__ import annotations

import os
from typing import Optional, Union, Mapping, Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, Connection


# ---------- DSN helpers ----------

def _get_secret(name: str, default: Optional[str] = None) -> Optional[str]:
    """
    Read a value from Streamlit secrets if available; else env vars.
    """
    try:
        import streamlit as st  # type: ignore
        return st.secrets.get(name, default)
    except Exception:
        return os.getenv(name, default)


def _dsn_from_secrets() -> Optional[str]:
    """
    Build a DSN string from secrets/env.
    Preference order:
      1) Direct DSN keys (CONN, CONN_POOL, CONN_DIRECT, CONN_STAGING, CONN_LOCAL)
      2) PG* parts (PGHOST/PGPORT/PGUSER/PGPASSWORD/PGDATABASE)
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

    if host and user and pwd:
        return f"postgresql+psycopg://{user}:{pwd}@{host}:{port}/{db}?sslmode=require"

    return None


# ---------- Engine factory ----------

def get_engine(dsn: Optional[str] = None) -> Engine:
    """
    Build a SQLAlchemy Engine.

    Preference order:
      1) explicit DSN arg
      2) DSN from secrets (CONN/CONN_POOL/etc.)
      3) PG* parts (if present)

    Raises:
      KeyError if no configuration is available.
    """
    url = (dsn or _dsn_from_secrets())
    if not url:
        raise KeyError(
            "Database config missing. Provide a DSN (e.g., CONN/CONN_POOL) "
            "or PG* parts in secrets/env."
        )

    # PGBouncer-friendly; harmless for direct connections
    return create_engine(
        url,
        pool_pre_ping=True,
        future=True,
        connect_args={"prepare_threshold": None},
    )


# ---------- Convenience helpers ----------

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