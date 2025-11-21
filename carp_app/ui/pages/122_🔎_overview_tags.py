# carp_app/ui/pages/122_🔎_overview_tags.py
from __future__ import annotations

import os
import pathlib
import sys
from typing import Optional, List

import pandas as pd
import streamlit as st
from sqlalchemy import text
from sqlalchemy.engine import Engine

# ───────── repo bootstrap ─────────
ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from carp_app.ui.lib.app_ctx import get_engine
from carp_app.ui.auth_gate import require_auth
from carp_app.ui.email_otp_gate import require_email_otp
try:
    from carp_app.ui.auth_gate import require_app_unlock
except Exception:
    def require_app_unlock(): ...


# ───────── auth & page ─────────
sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(
    page_title="CARP — Overview: Tags",
    page_icon="🏷️",
    layout="wide"
)
st.title("🏷️ Overview: Tags")


# ───────── engine (cached) ─────────
@st.cache_resource(show_spinner=False)
def _eng() -> Engine:
    url = os.getenv("DB_URL")
    if not url:
        st.error("DB_URL is not set")
        st.stop()
    return get_engine()


def _normalize(s: str | None) -> Optional[str]:
    s = (s or "").strip()
    return s or None


# ───────── filters ─────────
with st.form("filters", clear_on_submit=False):
    c1, c2 = st.columns([3, 1])
    with c1:
        q_raw = st.text_input(
            "Search tag_code / tag_name / localization / notes",
            "",
        )
    with c2:
        lim = int(
            st.number_input(
                "Limit",
                min_value=50,
                max_value=5000,
                value=1000,
                step=50,
            )
        )
    _ = st.form_submit_button("Apply")

q = _normalize(q_raw)


# ───────── canonical query: public.tags ─────────
sql = text("""
    SELECT
      id::text     AS id,
      tag_code,
      tag_name,
      localization,
      notes,
      created_at
    FROM public.tags
    WHERE (
         :q IS NULL
      OR  tag_code     ILIKE :ql
      OR  tag_name     ILIKE :ql
      OR  COALESCE(localization,'') ILIKE :ql
      OR  COALESCE(notes,'')        ILIKE :ql
    )
    ORDER BY tag_code
    LIMIT :limit;
""")

params = {
    "q": q,
    "ql": f"%{q}%" if q else None,
    "limit": lim,
}

with _eng().begin() as cx:
    df = pd.read_sql(sql, cx, params=params)

df = df.fillna("")
st.caption(f"{len(df)} tag(s)")


# ───────── read-only table + selection ─────────
view = df.copy()
view.insert(0, "✓ Select", False)

grid = st.data_editor(
    view,
    key="tags_overview_grid_v8",
    hide_index=True,
    use_container_width=True,
    num_rows="fixed",
    column_order=[
        "✓ Select",
        "tag_code",
        "tag_name",
        "localization",
        "notes",
        "created_at",
    ],
    column_config={
        "✓ Select":     st.column_config.CheckboxColumn("✓ Select", default=False),
        "tag_code":     st.column_config.TextColumn("Tag code", disabled=True),
        "tag_name":     st.column_config.TextColumn("Name", disabled=True),
        "localization": st.column_config.TextColumn("Localization", disabled=True),
        "notes":        st.column_config.TextColumn("Notes", disabled=True),
        "created_at":   st.column_config.DatetimeColumn("Created", disabled=True),
    },
)

selected_ids: List[str] = []
if isinstance(grid, pd.DataFrame) and "✓ Select" in grid.columns:
    selected_ids = grid.loc[grid["✓ Select"] == True, "id"].astype(str).tolist()

st.divider()
st.subheader("Edit selection")


# editable columns for tags (export-only)
c1, c2 = st.columns([2, 1])
with c1:
    editable_cols = st.multiselect(
        "Editable columns",
        ["tag_name", "localization", "notes"],
        default=[],
    )
with c2:
    st.caption("Selected rows:")
    st.write(f"**{len(selected_ids)}**")


if not selected_ids or not editable_cols:
    st.info("Select rows above and choose editable columns.")
else:
    to_edit = df[df["id"].isin(selected_ids)].reset_index(drop=True)

    colcfg = {
        "id":          st.column_config.TextColumn("ID", disabled=True),
        "tag_code":    st.column_config.TextColumn("Tag code", disabled=True),
        "tag_name":    st.column_config.TextColumn("Name", disabled=("tag_name" not in editable_cols)),
        "localization":st.column_config.TextColumn("Localization", disabled=("localization" not in editable_cols)),
        "notes":       st.column_config.TextColumn("Notes", disabled=("notes" not in editable_cols)),
        "created_at":  st.column_config.DatetimeColumn("Created", disabled=True),
    }

    edited_df = st.data_editor(
        to_edit,
        key="tags_edit_table_v8",
        hide_index=True,
        use_container_width=True,
        column_config=colcfg,
    )

    st.download_button(
        "⬇︎ Download Edited Rows (CSV)",
        data=edited_df.to_csv(index=False).encode("utf-8"),
        file_name="tags_edited.csv",
        type="primary",
    )


# Always allow export
st.download_button(
    "⬇︎ Download Full CSV",
    data=df.to_csv(index=False).encode("utf-8"),
    file_name="tags_overview.csv",
    type="secondary",
    mime="text/csv",
)
