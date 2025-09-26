# supabase/ui/lib/db.py

import os
from typing import Optional, Union, Mapping, Any
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, Connection

# ---------- DSN helpers ----------

def _dsn_from_secrets() -> Optional[str]:
    """Build a DSN from Streamlit secrets or env PG* vars."""
    try:
        import streamlit as st  # type: ignore
        get = lambda k, d=None: st.secrets.get(k, d)
    except Exception:
        get = lambda k, d=None: os.getenv(k, d)

    # Prefer explicit DSNs if present
    dsn = (get("CONN") or get("CONN_STAGING") or get("CONN_LOCAL"))
    if dsn and str(dsn).strip():
        return str(dsn).strip()

    # Otherwise build from PG* parts
    host = get("PGHOST")
    user = get("PGUSER")
    pwd  = get("PGPASSWORD")
    db   = get("PGDATABASE", "postgres")
    port = str(get("PGPORT", "5432"))

    if not (host and user and pwd):
        return None

    return f"postgresql+psycopg://{user}:{pwd}@{host}:{port}/{db}?sslmode=require"


# ---------- Engine factory ----------


def get_engine(_conn: Optional[str] = None):
    import os, streamlit as st

    if _conn:
        url = _conn
    else:
        host = st.secrets["PGHOST"]
        port = int(st.secrets.get("PGPORT", 5432))
        user = st.secrets["PGUSER"]
        pwd  = st.secrets["PGPASSWORD"]
        db   = st.secrets.get("PGDATABASE", "postgres")
        url = f"postgresql+psycopg://{user}:{pwd}@{host}:{port}/{db}?sslmode=require"

    engine = create_engine(
        url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=5,
        pool_recycle=1800,
        future=True,
        connect_args={
            # turn off server-side prepared statements to avoid DuplicatePreparedStatement
            "prepare_threshold": None,
        },
    )
    return engine


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
    """
    Read a SELECT into a pandas DataFrame.
    """
    import pandas as pd
    return pd.read_sql(text(sql), conn, params=params or {})


def exec_sql(conn: Union[Engine, Connection], sql: str, params: Optional[Mapping[str, Any]] = None):
    """
    Execute an arbitrary SQL statement. Works with Engine or Connection.
    """
    if isinstance(conn, Engine):
        with conn.begin() as cx:
            cx.execute(text(sql), params or {})
    else:
        conn.execute(text(sql), params or {})