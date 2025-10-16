import os, re, urllib.parse, streamlit as st

_REF_RE = re.compile(r"^db\.([a-z0-9]{20})\.supabase\.co$")

def _env_from_db_url(u: str):
    p = urllib.parse.urlparse(u or "")
    host = (p.hostname or "").lower()
    user = (p.username or "")  # e.g., postgres.zebzrvjbalhazztvhhcm
    # Try user-based ref first (pooler), else parse from host (direct db)
    proj = user.split(".", 1)[1] if "." in user else ""
    if not proj:
        m = _REF_RE.match(host)
        proj = m.group(1) if m else ""

    prod = os.getenv("PROD_PROJECT_ID", "").lower()
    stag = os.getenv("STAGING_PROJECT_ID", "").lower()

    if proj and proj == prod:
        env = "PROD"
    elif proj and proj == stag:
        env = "STAGING"
    elif "pooler.supabase.com" in host:
        env = "STAGING"  # pooler but unknown ref
    else:
        env = "LOCAL"

    return env, proj or "?", host or "?"

def show_env_badge():
    u = os.getenv("DB_URL", "")
    env, proj, host = _env_from_db_url(u)
    st.caption(f"Environment: {env} • Project: {proj} • Host: {host}")
