from __future__ import annotations
import os
import streamlit as st

# optional: load .env for local runs (no-op on Streamlit Cloud)
try:
    from dotenv import load_dotenv  # requires python-dotenv in requirements
    load_dotenv()
except Exception:
    pass

def get(name: str, default: str | None = None) -> str | None:
    # Streamlit Cloud uses st.secrets; local uses environment/.env
    if name in st.secrets:
        return st.secrets[name]
    return os.getenv(name, default)

DB_URL            = get("DB_URL")
SUPABASE_URL      = get("SUPABASE_URL")
SUPABASE_ANON_KEY = get("SUPABASE_ANON_KEY")
APP_ENV           = get("APP_ENV", "dev")
