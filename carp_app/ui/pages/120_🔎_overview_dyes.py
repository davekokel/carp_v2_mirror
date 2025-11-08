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
st.set_page_config(page_title="🧪 Overview dyes", page_icon="🧪", layout="wide")

@st.cache_resource(show_spinner=False)
def _eng(): 
    if not os.getenv("DB_URL"): 
        st.error("DB_URL not set"); st.stop()
    return get_engine()

with st.form("f"): 
    q = st.text_input("Search (name/alt_names/notes/localization)", "")
    lim = int(st.number_input("Limit", 100, 5000, 1000, 100))
    st.form_submit_button("Apply")

sql = text("""
  SELECT
    id::text    AS id,
    dye_name,
    COALESCE(excitation_nm,0) AS excitation_nm,
    COALESCE(emission_nm,0)   AS emission_nm,
    COALESCE(localization,'') AS localization,
    COALESCE(array_to_string(alt_names, ', '), '') AS alt_names,
    COALESCE(notes,'')        AS notes
  FROM public.dyes
  WHERE (:q = '' OR dye_name ILIKE :ql OR COALESCE(localization,'') ILIKE :ql OR COALESCE(notes,'') ILIKE :ql OR COALESCE(array_to_string(alt_names,','),'') ILIKE :ql)
  ORDER BY dye_name
  LIMIT :lim
""")
params = {"q": q, "ql": f"%{q}%", "lim": lim}
with _eng().begin() as cx:
    df = pd.read_sql(sql, cx, params=params)
st.caption(f"{len(df)} rows")
st.dataframe(df, hide_indentation=True, use_container_width=True)