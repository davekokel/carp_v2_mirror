from __future__ import annotations
import os, re
try:
    import streamlit as st
    _S = dict(getattr(st, "secrets", {}))
except Exception:
    _S = {}
def get_secret(key: str, default: str = "") -> str:
    v = os.getenv(key)
    if v is not None and v != "": return v
    v = _S.get(key, "")
    return v if isinstance(v,str) else default
def db_url() -> str:
    v = get_secret("DB_URL", "")
    if v: return v
    return "postgresql://postgres@127.0.0.1:5432/postgres?sslmode=disable"
def env_info() -> tuple[str,str,str,str]:
    url = db_url()
    m = re.match(r".*://([^:@]+)@([^/?]+)", url or "")
    pguser = m.group(1) if m else os.getenv("PGUSER","")
    pghost = m.group(2) if m else os.getenv("PGHOST","")
    proj = pguser.split(".",1)[1] if "." in (pguser or "") else "local"
    prod_id = get_secret("PROD_PROJECT_ID","")
    stag_id = get_secret("STAGING_PROJECT_ID","")
    if proj == prod_id or "prod" in (pghost or ""): env = "PROD"
    elif proj == stag_id or "staging" in (pghost or ""): env = "STAGING"
    else: env = "LOCAL"
    mode = get_secret("APP_MODE","") or ("readonly" if pguser.endswith("_ro") else "write")
    return env, proj, pghost or "127.0.0.1:5432", mode
