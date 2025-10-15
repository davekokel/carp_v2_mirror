from __future__ import annotations
from typing import Any, Dict, Iterable, List, Tuple
from pathlib import Path
import sys
import pandas as pd
import streamlit as st

# Ensure project root import works when pages run from /supabase/ui/pages
ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ------- Query params -------
def get_params() -> Dict[str, Any]:
    return dict(st.query_params)

def set_params(**kw: Any) -> None:
    st.query_params.clear()
    for k, v in kw.items():
        if v in (None, "", [], ()):
            continue
        st.query_params[k] = [str(x) for x in v] if isinstance(v, (list, tuple)) else str(v)

# ------- Search / filter helpers -------
def text_search(df: pd.DataFrame, q: str, cols: Iterable[str]) -> pd.DataFrame:
    if not q:
        return df
    q = q.strip().lower()
    mask = pd.Series(False, index=df.index)
    for c in cols:
        if c in df.columns:
            mask |= df[c].fillna("").astype(str).str.lower().str.contains(q, na=False)
    return df[mask]

# ------- KPIs -------
def kpi_row(kpis: List[Tuple[str, Any]]) -> None:
    cols = st.columns(len(kpis))
    for col, (label, value) in zip(cols, kpis):
        with col:
            st.metric(label, value if value not in (None, "") else "—")

# ------- Pagination -------
def paginate(df: pd.DataFrame, page: int, size: int) -> Tuple[pd.DataFrame, int, int]:
    total = len(df)
    pages = max(1, (total + size - 1) // size)
    page = max(1, min(page, pages))
    i0, i1 = (page - 1) * size, (page - 1) * size + size
    return df.iloc[i0:i1], pages, page

def pager_controls(page: int, pages: int, *, key: str = "pager") -> int:
    l, m, r = st.columns([1, 2, 1])
    new_page = page
    with l:
        if st.button("◀ Prev", key=f"{key}-prev", use_container_width=True, disabled=(page <= 1)):
            new_page = page - 1
    with m:
        st.write(f"Page {page} / {pages}")
    with r:
        if st.button("Next ▶", key=f"{key}-next", use_container_width=True, disabled=(page >= pages)):
            new_page = page + 1
    return new_page

# ------- CSV export -------
def download_csv(df: pd.DataFrame, *, filename: str, label: str = "Download CSV") -> None:
    st.download_button(
        label,
        data=df.to_csv(index=False).encode("utf-8"),
        file_name=filename,
        mime="text/csv",
        use_container_width=True,
    )

# ------- Page setup -------
def set_page(title: str, icon: str = "🐟", layout: str = "wide") -> None:
    st.set_page_config(page_title=title, page_icon=icon, layout=layout)
