import os
from carp_app.lib.secret import db_url, get_secret
from carp_app.lib.db import get_engine

DB_URL = db_url()
engine = get_engine

# optional: expose env details so Streamlit pages can read them
AUTH_MODE = get_secret("AUTH_MODE", "off")
STAGING_PROJECT_ID = get_secret("STAGING_PROJECT_ID", "")
PROD_PROJECT_ID = get_secret("PROD_PROJECT_ID", "")

_proj = ""
try:
    user_part = DB_URL.split("://",1)[1].split("@",1)[0]
    if "." in user_part:
        _proj = user_part.split(".",1)[1]
except Exception:
    pass

if _proj == PROD_PROJECT_ID or "prod" in DB_URL:
    env_name = "PROD"
elif _proj == STAGING_PROJECT_ID or "staging" in DB_URL:
    env_name = "STAGING"
else:
    env_name = "LOCAL"
