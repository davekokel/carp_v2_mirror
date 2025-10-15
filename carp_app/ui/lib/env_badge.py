import os, re, streamlit as st

def show_env_badge():
    db_url = os.getenv("DB_URL", "")
    user = host = proj = "?"
    m = re.match(r".*://([^:@]+)@([^/?]+)", db_url)
    if m:
        user, host = m.group(1), m.group(2)
        proj = user.split(".", 1)[1] if "." in user else "?"

    is_local = host.startswith("127.") or host.startswith("localhost")
    env_name = (
        "LOCAL"   if is_local else
        ("PROD"    if ("prod" in host or proj in os.getenv("PROD_PROJECT_ID","")) else
         "STAGING" if ("staging" in host or proj in os.getenv("STAGING_PROJECT_ID","")) else
         "LOCAL")
    )
    if is_local:
        proj = "local"

    st.caption(f"Environment: {env_name} • Project: {proj} • Host: {host}")
