# carp_app/ui/pages/100_🧪_overview_plasmids.py
from __future__ import annotations
import os, pathlib, sys
from typing import Optional

import pandas as pd
import streamlit as st
from sqlalchemy import text
from sqlalchemy.engine import Engine

# repo root on sys.path
ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from carp_app.ui.auth_gate import require_auth
from carp_app.ui.email_otp_gate import require_email_otp
try:
    from carp_app.ui.auth_gate import require_app_unlock
except Exception:
    def require_app_unlock(): ...
from carp_app.ui.lib.app_ctx import get_engine as _create_engine

# ───────────── auth & page ─────────────
sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(page_title="CARP — Plasmids Overview", page_icon="🧪", layout="wide")
st.title("🧪 Plasmids Overview")

# ───────────── engine cache ────────────
@st.cache_resource(show_spinner=False)
def _cached_engine() -> Engine:
    url = os.environ.get("DB_URL")
    if not url:
        raise RuntimeError("DB_URL not set")
    return _create_engine()

def _get_engine() -> Engine:
    return _cached_engine()

# ───────────── data loaders ────────────
def _coerce_strings(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    for c in df.select_dtypes(include=["object", "string"]).columns:
        df[c] = df[c].astype("string").fillna("")
    return df

def _load_plasmids_overview(q: Optional[str], limit: int) -> pd.DataFrame:
    """
    Load plasmids from v_plasmids_overview.

    We keep `name` and `tag_codes` available for search, but we don't show or edit
    them in the main grids; the user-facing fields are:
      - code
      - nickname
      - resistance
      - fluors (rolled up)
      - fusions (rolled up)
      - n_fusions
      - created_at
    """
    sql = text("""
      SELECT
        code,
        name,
        nickname,
        resistance,
        fluors,
        tag_codes,
        fusions,
        n_fusions,
        created_at
      FROM public.v_plasmids_overview v
      WHERE (:q IS NULL)
         OR (
              v.code       ILIKE :q
           OR v.name       ILIKE :q
           OR v.nickname   ILIKE :q
           OR v.resistance ILIKE :q
           OR v.fluors     ILIKE :q
           OR v.tag_codes  ILIKE :q
           OR v.fusions    ILIKE :q
         )
      ORDER BY v.created_at DESC NULLS LAST, v.code
      LIMIT :lim
    """)
    params = {
        "q":   (f"%{q.strip()}%" if q and q.strip() else None),
        "lim": int(limit),
    }
    with _get_engine().begin() as cx:
        df = pd.read_sql(sql, cx, params=params)
    return _coerce_strings(df)

# ─────────────────────────── page ───────────────────────────
def main():
    st.caption(f"DB_URL = {os.getenv('DB_URL','')}")

    # Filters
    with st.form("plasmid_filters", clear_on_submit=False):
        c1, c2 = st.columns([3, 1])
        with c1:
            q = st.text_input(
                "Search (code / nickname / resistance / fluors / fusions)",
                ""
            )
        with c2:
            limit = int(st.number_input("Limit", min_value=10, max_value=2000, value=500, step=50))
        _ = st.form_submit_button("Search")

    df = _load_plasmids_overview(q, limit)
    if df.empty:
        st.info("No plasmids match your filters.")
        return

    st.subheader(f"Plasmids ({len(df)} rows)")

    # Show all columns from the view so we can inspect everything
    table = df.copy()

    st.dataframe(table, width="stretch", hide_index=True)

    st.divider()
    st.subheader("Edit selection")

    # Only allow editing of nickname + resistance here
    editable_map = {
        "nickname":   "Nickname",
        "resistance": "Resistance",
    }
    edit_choice = st.multiselect(
        "Choose which columns are editable",
        list(editable_map.keys()),
        []
    )

    selected = st.data_editor(
        table,
        width="stretch",
        hide_index=True,
        disabled=[c for c in table.columns if c not in edit_choice],
        key="plasmids_editor_v1",
    )

    if st.button("Save edits", type="primary"):
        if not edit_choice:
            st.info("No columns selected for editing.")
        else:
            changed = selected[[c for c in edit_choice] + ["code"]]
            changed = changed[changed["code"].notna()]
            if not changed.empty:
                with _get_engine().begin() as cx:
                    for _, row in changed.drop_duplicates(subset=["code"])[["code"] + list(edit_choice)].iterrows():
                        cx.execute(text(f"""
                          UPDATE public.plasmids
                          SET {", ".join([f"{c} = :{c}" for c in edit_choice])}
                          WHERE code = :code
                        """), {
                            **{c: (row[c] if pd.notna(row[c]) else None) for c in edit_choice},
                            "code": row["code"],
                        })
                st.success("Edits saved.")

if __name__ == "__main__":
    main()