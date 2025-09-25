import streamlit as st
import pandas as pd
from sqlalchemy import text
from lib_shared import env_selector, make_engine

st.set_page_config(page_title="CARP – Details", layout="wide")

conn_uri = env_selector("Local")
st.title("CARP Treatments — Detailed Listing")

if not conn_uri:
    st.info("Configure connections in `.streamlit/secrets.toml` under `[local]` and/or `[staging]`.")
    st.stop()

engine = make_engine(conn_uri)

# ---- Filters ----
st.subheader("Filters")
q_name = st.text_input("Fish name (ILIKE)", value="")
q_code = st.text_input("Code (ILIKE)", value="")
q_type = st.multiselect(
    "Type",
    options=["injected_plasmid", "injected_rna", "dye"],
)

base_sql = """
select
  f.name as fish_name,
  t.treatment_type::text as treatment_type,
  t.code,
  t.operator,
  t.notes,
  t.performed_at::date as performed_on
from public.treatments t
join public.fish_treatments ft on ft.treatment_id=t.id
join public.fish f on f.id = ft.fish_id
where 1=1
  {name_filter}
  {code_filter}
  {type_filter}
order by fish_name, treatment_type, performed_on
"""

name_filter = "and f.name ilike :name" if q_name else ""
code_filter = "and t.code ilike :code" if q_code else ""
type_filter = "and t.treatment_type::text = any(:types)" if q_type else ""

sql = base_sql.format(
    name_filter=name_filter, code_filter=code_filter, type_filter=type_filter
)

params = {}
if q_name:
    params["name"] = f"%{q_name}%"
if q_code:
    params["code"] = f"%{q_code}%"
if q_type:
    params["types"] = q_type

with engine.connect() as cx:
    detail_df = pd.read_sql(text(sql), cx, params=params)

st.subheader("Results")
st.dataframe(detail_df, hide_index=True, use_container_width=True)
st.download_button(
    "Download detailed CSV",
    detail_df.to_csv(index=False).encode("utf-8"),
    file_name="treatments_detailed.csv",
    mime="text/csv",
)