from __future__ import annotations

import sys
import pathlib

import pandas as pd
import streamlit as st
from sqlalchemy import text

ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from carp_app.ui.auth_gate import require_auth
from carp_app.ui.email_otp_gate import require_email_otp
try:
    from carp_app.ui.auth_gate import require_app_unlock
except Exception:
    def require_app_unlock() -> None:
        ...

from carp_app.ui.lib.page_engine import engine

st.set_page_config(
    page_title="CARP — Overview transgenes & alleles",
    page_icon="🧬",
    layout="wide",
)

sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.title("🧬 Overview transgenes & alleles")

# ---- summary query ----------------------------------------------------------
summary_sql = """
SELECT
  t.transgene_base_code,
  COALESCE(t.name, '')    AS transgene_name,
  count(ta.*)             AS n_alleles
FROM public.transgenes t
LEFT JOIN public.transgene_alleles ta
  ON ta.transgene_base_code = t.transgene_base_code
GROUP BY t.transgene_base_code, t.name
ORDER BY t.transgene_base_code;
"""

try:
    with engine().begin() as cx:
        summary_rows = cx.execute(text(summary_sql)).mappings().all()
except Exception as e:
    st.error("Error querying transgenes / alleles summary.")
    st.exception(e)
    st.stop()

summary_df = pd.DataFrame(summary_rows)

if summary_df.empty:
    st.info("No transgenes found in this database (transgene_alleles may be empty).")
else:
    st.subheader("Transgene summary")
    st.dataframe(summary_df, width="stretch")

# ---- sidebar filters --------------------------------------------------------
st.sidebar.header("Filters")

base_code_filter = st.sidebar.text_input("Transgene base code contains", "")
allele_number_filter = st.sidebar.text_input("Allele number equals (optional)", "")

limit = st.sidebar.number_input(
    "Max rows",
    min_value=100,
    max_value=5000,
    value=1000,
    step=100,
)

# ---- build WHERE clause -----------------------------------------------------
params: dict[str, object] = {"limit": int(limit)}
where_clauses = ["1=1"]

if base_code_filter.strip():
    where_clauses.append("ta.transgene_base_code ILIKE :base_code")
    params["base_code"] = f"%{base_code_filter.strip()}%"

if allele_number_filter.strip():
    where_clauses.append("ta.allele_number = :allele_number")
    try:
        params["allele_number"] = int(allele_number_filter.strip())
    except ValueError:
        st.warning("Allele number filter must be an integer.")
        st.stop()

where_sql = " AND ".join(where_clauses)

# ---- main query -------------------------------------------------------------
query_sql = f"""
SELECT
  ta.transgene_base_code,
  COALESCE(t.name, '')            AS transgene_name,
  ta.allele_number,
  COALESCE(ta.allele_name, '')     AS allele_name,
  COALESCE(ta.allele_nickname, '') AS allele_nickname
FROM public.transgene_alleles ta
LEFT JOIN public.transgenes t
  ON t.transgene_base_code = ta.transgene_base_code
WHERE {where_sql}
ORDER BY ta.transgene_base_code, ta.allele_number
LIMIT :limit;
"""

try:
    with engine().begin() as cx:
        rows = cx.execute(text(query_sql), params).mappings().all()
except Exception as e:
    st.error("Error loading transgene alleles.")
    st.exception(e)
    st.stop()

st.subheader("Transgene alleles")

if not rows:
    st.info("No alleles matched the current filters.")
else:
    df = pd.DataFrame(rows)

    preferred_cols = [
        "transgene_base_code",
        "transgene_name",
        "allele_number",
        "allele_name",
        "allele_nickname",
    ]
    existing = [c for c in preferred_cols if c in df.columns]
    df = df[existing]

    st.dataframe(df, width="stretch")

    csv_bytes = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Download transgene alleles as CSV",
        data=csv_bytes,
        file_name="transgenes_overview_filtered.csv",
        mime="text/csv",
    )

    st.caption(
        "Showing "
        f"{len(df)} rows (limit {limit}) "
        "from transgene_alleles with the current filters."
    )