from __future__ import annotations
import re
from sqlalchemy import create_engine
from carp_app.lib import secret

DB_URL = secret.get("DB_URL", "")
AUTH_MODE = secret.get("AUTH_MODE", "off")
STAGING_PROJECT_ID = secret.get("STAGING_PROJECT_ID", "")
PROD_PROJECT_ID = secret.get("PROD_PROJECT_ID", "")

def _parse_db_url(db_url: str):
    m = re.match(r".*://([^:@]+)@([^/?]+)", db_url or "")
    user = m.group(1) if m else ""
    host = m.group(2) if m else ""
    proj = user.split(".", 1)[1] if "." in user else ""
    return user, host, proj

def env_name(db_url: str | None = None) -> str:
    user, host, proj = _parse_db_url(db_url if db_url is not None else DB_URL)
    if proj and proj == PROD_PROJECT_ID or "prod" in host:
        return "PROD"
    if proj and proj == STAGING_PROJECT_ID or "staging" in host:
        return "STAGING"
    return "LOCAL"

def engine(db_url: str | None = None):
    url = (db_url if db_url is not None else DB_URL)
    return create_engine(url, pool_pre_ping=True, future=True)
