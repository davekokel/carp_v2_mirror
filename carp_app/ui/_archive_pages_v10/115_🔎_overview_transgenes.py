from __future__ import annotations

import sys
import pathlib
from typing import Dict, Any

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
  transgene_base_code,
  transgene_name,
  n_alleles
FROM public.v_transgenes_overview
ORDER BY transgene_base_code;
"""

try:
    with engine().begin() as cx:
        summary_rows = cx.execute(text(summary_sql)).mappings().all()
except Exception as e:
    st.error("Error querying transgenes / alleles summary.")
    st.exception(e)
    st.stop()

summary_df = pd.DataFrame(summary_rows)

selected_base_code: str | None = None

if summary_df.empty:
    st.info("No transgenes found in this database (transgene_alleles may be empty).")
else:
    st.subheader("Transgene summary")

    summary_view = summary_df.copy()
    if "✓ Select" not in summary_view.columns:
        summary_view.insert(0, "✓ Select", False)

    summary_edited = st.data_editor(
        summary_view,
        hide_index=True,
        use_container_width=True,
        num_rows="fixed",
        column_config={
            "✓ Select": st.column_config.CheckboxColumn("✓ Select", default=False),
            "transgene_base_code": st.column_config.TextColumn(
                "transgene_base_code", disabled=True
            ),
            "transgene_name": st.column_config.TextColumn(
                "transgene_name", disabled=True
            ),
            "n_alleles": st.column_config.NumberColumn(
                "n_alleles", disabled=True, format="%d"
            ),
        },
        key="transgene_summary_editor",
    )

    # Robust selection mask (avoid .get returning weird types)
    if isinstance(summary_edited, pd.DataFrame) and "✓ Select" in summary_edited.columns:
        sel_series = summary_edited["✓ Select"]
        if not isinstance(sel_series, pd.Series):
            sel_series = pd.Series(sel_series, index=summary_edited.index)
    else:
        sel_series = pd.Series(False, index=summary_df.index)

    sel_mask = sel_series.fillna(False).astype(bool)
    selected_rows = summary_edited.loc[sel_mask]

    if not selected_rows.empty:
        selected_base_code = str(
            selected_rows.iloc[0]["transgene_base_code"]
        ).strip() or None
        st.caption(f"Drill-down: showing alleles for **{selected_base_code}** below.")
    else:
        st.caption("Tip: check a row above to drill down into its alleles.")

# ---- sidebar filters --------------------------------------------------------
st.sidebar.header("Filters")

base_code_filter = st.sidebar.text_input(
    "Transgene base code contains (ignored when a transgene is selected above)", ""
)
allele_number_filter = st.sidebar.text_input("Allele number equals (optional)", "")

limit = st.sidebar.number_input(
    "Max rows",
    min_value=100,
    max_value=5000,
    value=1000,
    step=100,
)

# ---- build WHERE clause -----------------------------------------------------
params: Dict[str, Any] = {"limit": int(limit)}
where_clauses = ["1=1"]

if selected_base_code:
    where_clauses.append("transgene_base_code = :selected_base_code")
    params["selected_base_code"] = selected_base_code
elif base_code_filter.strip():
    where_clauses.append("transgene_base_code ILIKE :base_code")
    params["base_code"] = f"%{base_code_filter.strip()}%"

if allele_number_filter.strip():
    try:
        params["allele_number"] = int(allele_number_filter.strip())
        where_clauses.append("allele_number = :allele_number")
    except ValueError:
        st.warning("Allele number filter must be an integer.")
        st.stop()

where_sql = " AND ".join(where_clauses)

# ---- main query -------------------------------------------------------------
query_sql = f"""
SELECT
  transgene_base_code,
  transgene_name,
  allele_number,
  allele_name,
  allele_nickname
FROM public.v_transgene_alleles_overview
WHERE {where_sql}
ORDER BY transgene_base_code, allele_number
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
    if selected_base_code:
        st.info(f"No alleles found for transgene **{selected_base_code}**.")
    else:
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
        "from v_transgene_alleles_overview with the current filters."
    )