import os
try:
    import streamlit as st
    _secrets = dict(st.secrets)
except Exception:
    _secrets = {}
def get(key: str, default: str = "") -> str:
    return os.getenv(key, _secrets.get(key, default))
