from __future__ import annotations
from carp_app.lib.config import engine as get_engine
from carp_app.ui.auth_gate import require_auth
sb, session, user = require_auth()

from carp_app.ui.email_otp_gate import require_email_otp
require_email_otp()

import os, sys
from pathlib import Path
import pandas as pd
import streamlit as st
from carp_app.lib.db import get_engine, text

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

st.set_page_config(page_title="CARP — Audit Viewer", page_icon="🕵️", layout="wide")
st.title("🕵️ Audit Viewer")

DB_URL = os.environ.get("DB_URL")
if not DB_URL:
    st.error("DB_URL not set"); st.stop()

eng = get_engine()

with st.sidebar:
    st.caption("Filters")
    table = st.text_input("Table (contains)", value="")
    op = st.multiselect("Ops", ["I","U","D"], default=["I","U","D"])
    limit = st.number_input("Limit", min_value=10, max_value=5000, value=200, step=50)

q = text("""
select
  at,
  table_name,
  op,
  user_name,
  row_pk,
  left(coalesce(to_jsonb(new_row)::text,'') || coalesce(to_jsonb(old_row)::text,''), 200) as preview
from audit.writes
where (:t = '' or table_name ilike :tpat)
  and op = any(:ops)
order by at desc
limit :lim
""")

with eng.begin() as cx:
    df = pd.read_sql(q, cx, params={
        "t": table, "tpat": f"%{table}%", "ops": op, "lim": int(limit)
    })

st.dataframe(df, use_container_width=True, hide_index=True)
