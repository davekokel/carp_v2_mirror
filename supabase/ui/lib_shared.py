# supabase/ui/lib_shared.py

import os
from typing import Optional, Tuple, Dict
import streamlit as st


def _get_secret(key: str, default: Optional[str] = None) -> Optional[str]:
    """Read from Streamlit secrets; fall back to env var."""
    try:
        val = st.secrets.get(key)  # type: ignore[attr-defined]
        if val is None or (isinstance(val, str) and val.strip() == ""):
            raise KeyError
        return str(val)
    except Exception:
        v = os.getenv(key)
        return v if (v and v.strip()) else default


def _first_nonempty(*vals: Optional[str]) -> Optional[str]:
    for v in vals:
        if v and str(v).strip():
            return str(v).strip()
    return None


def _build_dsn_from_pg_parts() -> Optional[str]:
    """Build a SQLAlchemy DSN from PG* pieces in secrets/env. Return None if incomplete."""
    host = _get_secret("PGHOST")
    user = _get_secret("PGUSER")
    pwd  = _get_secret("PGPASSWORD")
    db   = _get_secret("PGDATABASE", "postgres")
    port = _get_secret("PGPORT", "5432")

    if not (host and user and pwd):
        return None

    # Always require SSL for Supabase / cloud connections
    return f"postgresql+psycopg://{user}:{pwd}@{host}:{port}/{db}?sslmode=require"


def pick_environment() -> Tuple[str, Optional[str]]:
    """
    Decide which environment is active and return (env_name, dsn_or_none).

    Priority for DSN:
      - ENV_NAME == "staging": CONN_STAGING -> CONN -> build from PG*
      - ENV_NAME == "local":   CONN_LOCAL   -> CONN -> build from PG*
      - Otherwise:             CONN         -> build from PG*
    """
    env_name = _get_secret("ENV_NAME", os.getenv("ENV_NAME", "staging")).lower()

    dsn: Optional[str] = None
    if env_name == "staging":
        dsn = _first_nonempty(
            _get_secret("CONN_STAGING"),
            _get_secret("CONN"),
            _build_dsn_from_pg_parts(),
        )
    elif env_name == "local":
        dsn = _first_nonempty(
            _get_secret("CONN_LOCAL"),
            _get_secret("CONN"),
            _build_dsn_from_pg_parts(),
        )
    else:
        dsn = _first_nonempty(
            _get_secret("CONN"),
            _build_dsn_from_pg_parts(),
        )

    return env_name, dsn


# --- put this in supabase/ui/lib_shared.py --
from typing import Optional, Dict, Any, List

def parse_query(raw: Optional[str] = None) -> Dict[str, Any]:
    """
    Parse compact query text.
    Tokens (case-insensitive):
      - batch:<value>
      - search:<value with spaces ok via quotes or underscores>
      - limit:<n>
      - mode:and|or   (alias: mode:any -> OR)
    Free tokens (no k:v) are treated as search terms.
    Returns:
      {
        "batch": Optional[str],
        "search": Optional[str],   # space-joined string of terms
        "terms": List[str],        # individual tokens
        "limit": Optional[int],
        "mode": "AND" | "OR",
      }
    """
    result: Dict[str, Any] = {
        "batch": None,
        "search": None,
        "terms": [],
        "limit": None,
        "mode": "AND",
    }
    if not raw:
        return result

    s = str(raw).strip()
    if not s:
        return result

    tokens = s.split()
    terms: List[str] = []

    for t in tokens:
        if ":" in t:
            k, v = t.split(":", 1)
            k = k.lower().strip()
            v = v.strip().strip('"').strip("'")
            if k == "batch" and v:
                result["batch"] = v
                continue
            if k == "search" and v:
                terms.append(v)
                continue
            if k == "limit" and v.isdigit():
                result["limit"] = int(v)
                continue
            if k == "mode" and v:
                mv = v.upper()
                result["mode"] = "OR" if mv in ("OR", "ANY") else "AND"
                continue
        # otherwise treat as free term
        if t.strip():
            terms.append(t.strip())

    result["terms"] = terms
    result["search"] = " ".join(terms) if terms else None
    return result