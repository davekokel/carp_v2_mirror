from __future__ import annotations
import os, sys
from pathlib import Path
import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
st.set_page_config(page_title="CARP — Overview Crosses", page_icon="🧬", layout="wide")
st.title("🧬 Overview — Crosses")

DB_URL = os.getenv("DB_URL"); 
if not DB_URL: st.error("DB_URL not set"); st.stop()
eng = create_engine(DB_URL, future=True, pool_pre_ping=True)

CANDS = [
    ("view","public.v_crosses_status","select * from public.v_crosses_status"),
    ("view","public.vw_crosses_status","select * from public.vw_crosses_status"),
    ("table","public.cross_instances","select * from public.cross_instances"),
    ("table","public.planned_crosses","select * from public.planned_crosses"),
]
def exists(name:str)->bool:
    sch,tab = name.split(".",1)
    q = text("""select 1
      where exists(select 1 from information_schema.tables where table_schema=:s and table_name=:t)
         or exists(select 1 from information_schema.views  where table_schema=:s and table_name=:t)""")
    with eng.begin() as cx: 
        return bool(pd.read_sql(q,cx,params={"s":sch,"t":tab}).shape[0])

src = next((sql for _,name,sql in CANDS if exists(name)), None)
if not src: st.info("No crosses table/view found."); st.stop()

with eng.begin() as cx: df = pd.read_sql(text(src), cx)
if df.empty: st.info("No crosses yet."); st.stop()

c1,c2,c3 = st.columns(3)
q = c1.text_input("Search", "")
d1 = c2.date_input("From", value=None)
d2 = c3.date_input("To", value=None)

f = df.copy()
if q:
    ql = q.lower()
    f = f[[ql in " ".join(map(lambda x:str(x).lower(), row)) for row in f.to_numpy()]]
for col in ["date","planned_date","created_at"]:
    if col in f.columns and d1: f = f[f[col].astype("string") >= str(d1)]
    if col in f.columns and d2: f = f[f[col].astype("string") <= str(d2)]

st.dataframe(f, use_container_width=True, hide_index=True)
