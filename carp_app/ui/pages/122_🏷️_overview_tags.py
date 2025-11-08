from __future__ import annotations
import sys, pathlib, os
sys.path.append(str(pathlib.Path(__file__).resolve().parents[3]))

import pandas as pd, streamlit as st
from sqlalchemy import text
from carp_app.ui.lib.app_ctx import get_engine
from carp_app.ui.auth_gate import require_auth
from carp_app.ui.email_otp_gate import require_email_otp
try:
    from carp_app.ui.auth_gate import require_app_unlock
except Exception:
    def require_app_unlock(): ...
sb, _, _ = require_auth(); require_email_otp(); require_app_unlock()
st.set_page_config(page_title="🏷️ Overview tags", page_icon="🏷️", layout="wide")

@st.cache_resource(show_spinner=False)
def _eng():
    if not os.getenv("DB_URL"): 
        st.error("DB_URL not set"); st.stop()
    return get_engine()

with st.form("f"): 
    q = st.text_input("Search (tag/name/citation)", "")
    lim = int(st.number_input("Limit", min_value=100, max_value=5000, value=1000, step=100))
    st.form_submit_button("Apply")

sql = text("""
  SELECT
    id::text    AS id,
    COALESCE(tag_name,'')   AS tag_name,
    COALESCE(tag_code,'')   AS tag_code,
    COALESCE(localization,'') AS localization,
    COALESCE(citation_link,'') AS citation_link,
    COALESCE(note,'')       AS note
  FROM public.tags
  WHERE (:q = '' OR tag_name ILIKE :ql OR COALESCE(tag_code,'') ILIKE :ql OR COALESCE(note,'') ILIKE :ql OR COALESCE(citation_link,'') ILIKE :ql)
  ORDER BY tag_name, tag_code
  LIMIT :lim
""")
params = {"q": q, "ql": f"%{q}%", "lim": lim}
with _eng().begin() as cx:
    df = pd.read_sql(sql, cx, params=params)
st.caption(f"{len(df)} rows")
st.dataframe(df, hide_indentation=True, use_container_width=True)