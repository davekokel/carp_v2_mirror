from __future__ import annotations
import pandas as pd
import streamlit as st
from typing import Optional, Tuple
from sqlalchemy.engine import Engine
from supabase import queries as Q
PAGE_SIZE_DEFAULT = 50
def overview_browser(
    engine: Engine,
    key: str,
    max_rows: int = 300,
    page_size: int = PAGE_SIZE_DEFAULT,
    show_columns: Optional[list[str]] = None,
) -> Tuple[pd.DataFrame, list[str]]:
    q_key = f"q_{key}"
    df_key = f"df_{key}"
    q = st.text_input("Search (code/name/transgene…)", value=st.session_state.get(q_key, ""), key=q_key)
    if st.button("Search", key=f"search_{key}"):
        st.session_state.pop(df_key, None)
    if df_key in st.session_state:
        df_accum = st.session_state[df_key]
    else:
        df_accum = pd.DataFrame()
        total = None
        page = 1
        while len(df_accum) < max_rows:
            t, df = Q.load_fish_overview(engine, page=page, page_size=page_size, q=(q or None))
            if total is None:
                total = t
            if df.empty:
                break
            if show_columns:
                cols = [c for c in show_columns if c in df.columns]
                if cols:
                    df = df[cols]
            if "fish_code" not in df.columns:
                break
            df_accum = pd.concat([df_accum, df], ignore_index=True)
            df_accum = df_accum.drop_duplicates(subset=["fish_code"], keep="first")
            if len(df) < page_size:
                break
            page += 1
        st.session_state[df_key] = df_accum
    df_accum = st.session_state.get(df_key, pd.DataFrame())
    if df_accum.empty:
        st.info("No results.")
        return df_accum, []
    if "__pick__" not in df_accum.columns:
        df_accum["__pick__"] = False
    view_cols = ["__pick__"] + [c for c in df_accum.columns if c != "__pick__"]
    edited = st.data_editor(
        df_accum[view_cols],
        width="stretch",
        height=400,
        hide_index=True,
        column_config={"__pick__": st.column_config.CheckboxColumn("Pick", help="Check rows to select")},
        disabled=[c for c in view_cols if c != "__pick__"]
    )
    picked = edited.loc[edited["__pick__"] == True, "fish_code"].astype(str).tolist()
    return edited.drop(columns=["__pick__"], errors="ignore"), picked
