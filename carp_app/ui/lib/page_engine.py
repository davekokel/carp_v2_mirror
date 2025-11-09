# carp_app/ui/lib/page_engine.py
from __future__ import annotations

import os
import streamlit as st
from sqlalchemy.engine import Engine
from carp_app.ui.lib.app_ctx import get_engine as _create_engine

@st.cache_resource(show_spinner=False)
def engine() -> Engine:
    """
    Canonical, cached SQLAlchemy Engine for Streamlit pages.
    Requires DB_URL to be set in the environment.
    """
    url = os.getenv("DB_URL", "")
    if not url:
        st.error("DB_URL is not set in the environment")
        st.stop()
    return _create_engine()