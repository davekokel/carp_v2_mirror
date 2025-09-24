import streamlit as st
from sqlalchemy import create_engine, text
import pandas as pd

@st.cache_resource
def get_engine(conn_str: str):
    return create_engine(conn_str)

def fetch_df(cx, sql: str, params=None) -> pd.DataFrame:
    return pd.read_sql(text(sql), cx, params=params or {})

def exec_sql(cx, sql: str, params=None):
    return cx.execute(text(sql), params or {})
