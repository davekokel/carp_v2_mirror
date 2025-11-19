# carp_app/ui/pages/122_🔎_overview_tags.py
from __future__ import annotations

import sys, pathlib, os
from typing import Optional, List

import pandas as pd
import streamlit as st
from sqlalchemy import text
from sqlalchemy.engine import Engine

# repo root on sys.path
ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# app libs / auth
from carp_app.ui.lib.app_ctx import get_engine
from carp_app.ui.auth_gate import require_auth
from carp_app.ui.email_otp_gate import require_email_otp
try:
    from carp_app.ui.auth_gate import require_app_unlock
except Exception:
    def require_app_unlock(): ...

# gate
sb, _, _ = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(
    page_title="CARP — Overview: Tags",
    page_icon="🔎",
    layout="wide",
)
st.title("🔎 Overview: Tags")

# engine (cached)
@st.cache_resource(show_spinner=False)
def _eng() -> Engine:
    url = os.getenv("DB_URL", "")
    if not url:
        st.error("DB_URL is not set")
        st.stop()
    return get_engine()

def _normalize_q(s: str | None) -> Optional[str]:
    s = (s or "").strip()
    return s or None

# ── Filters ───────────────────────────────────────────────────────────────────
with st.form("filters", clear_on_submit=False):
    c1, c2 = st.columns([3, 1])
    with c1:
        q_raw = st.text_input(
            "Search (code / name / alt names / localization / note / citation link)",
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

q = _normalize_q(q_raw)

# ── Query ────────────────────────────────────────────────────────────────────
sql = text(
    """
    SELECT
      id::text                      AS id,
      COALESCE(tag_code, '')        AS code,
      COALESCE(tag_name, '')        AS name,
      COALESCE(
        array_to_string(alt_names, ', '),
        ''
      )                             AS alt_names,
      COALESCE(localization, '')    AS localization,
      COALESCE(notes, '')           AS note,
      ''::text                      AS citation_link,
      created_at
    FROM public.tags
    WHERE
      (
        :q IS NULL
        OR COALESCE(tag_code, '')                     ILIKE :ql
        OR COALESCE(tag_name, '')                     ILIKE :ql
        OR COALESCE(
             array_to_string(alt_names, ', '),
             ''
           )                                          ILIKE :ql
        OR COALESCE(localization, '')                 ILIKE :ql
        OR COALESCE(notes, '')                        ILIKE :ql
      )
    ORDER BY tag_name, tag_code
    LIMIT :lim
    """
)
params = {"q": q, "ql": f"%{q}%" if q else None, "lim": lim}

with _eng().begin() as cx:
    df = pd.read_sql(sql, cx, params=params)

st.caption(f"{len(df)} tag(s)")

# ── Read-only overview with row selector ─────────────────────────────────────
ro = df.copy()
ro.insert(0, "✓ Select", False)

ro_view = st.data_editor(
    ro,
    key="tags_overview_readonly",
    use_container_width=True,
    hide_index=True,
    column_config={
        "id":            st.column_config.TextColumn("ID", disabled=True),
        "code":          st.column_config.TextColumn("Code", disabled=True),
        "name":          st.column_config.TextColumn("Name", disabled=True),
        "alt_names":     st.column_config.TextColumn("Alt names", disabled=True),
        "localization":  st.column_config.TextColumn("Localization", disabled=True),
        "note":          st.column_config.TextColumn("Note", disabled=True),
        "citation_link": st.column_config.LinkColumn("Citation link", disabled=True),
        "created_at":    st.column_config.DatetimeColumn("Created at", disabled=True),
        "✓ Select":      st.column_config.CheckboxColumn("✓ Select"),
    },
)

# ── Edit gate: must pick rows AND columns first ──────────────────────────────
selected_ids: List[str] = []
if isinstance(ro_view, pd.DataFrame) and "✓ Select" in ro_view.columns:
    selected_ids = (
        ro_view.loc[ro_view["✓ Select"] == True, "id"]
        .astype(str)
        .tolist()
    )

st.divider()
st.subheader("Edit selection")

col_left, col_right = st.columns([2, 1])
with col_left:
    st.caption("1) Choose which columns are editable")
    editable_cols = st.multiselect(
        "Editable columns",
        ["code", "name", "alt_names", "localization", "note", "citation_link"],
        default=[],
    )
with col_right:
    st.caption("2) You must select rows above")
    st.write(f"Selected rows: **{len(selected_ids)}**")

if not selected_ids or not editable_cols:
    st.info(
        "Select at least one row in the table above **and** choose one or more "
        "editable columns."
    )
else:
    to_edit = df[df["id"].isin(selected_ids)].reset_index(drop=True)

    colcfg = {
        "id":           st.column_config.TextColumn("ID", disabled=True),
        "code":         st.column_config.TextColumn(
            "Code", disabled=("code" not in editable_cols)
        ),
        "name":         st.column_config.TextColumn(
            "Name", disabled=("name" not in editable_cols)
        ),
        "alt_names":    st.column_config.TextColumn(
            "Alt names", disabled=("alt_names" not in editable_cols)
        ),
        "localization": st.column_config.TextColumn(
            "Localization", disabled=("localization" not in editable_cols)
        ),
        "note":         st.column_config.TextColumn(
            "Note", disabled=("note" not in editable_cols)
        ),
        "citation_link": st.column_config.LinkColumn(
            "Citation link", disabled=("citation_link" not in editable_cols)
        ),
        "created_at":   st.column_config.DatetimeColumn(
            "Created at", disabled=True
        ),
    }

    st.caption(
        "3) Edit the selected rows (changes are not persisted; export to CSV below)"
    )
    edited = st.data_editor(
        to_edit,
        key="tags_overview_editor",
        use_container_width=True,
        hide_index=True,
        column_config=colcfg,
    )

    st.download_button(
        "⬇︎ Download Edited Rows (CSV)",
        data=edited.to_csv(index=False).encode("utf-8"),
        file_name=f"tags_edited_{len(edited)}_{('all' if not q else q)}.csv",
        type="primary",
        mime="text/csv",
    )

# Always allow export of the current overview
st.download_button(
    "⬇︎ Download Full CSV",
    data=df.to_csv(index=False).encode("utf-8"),
    file_name=f"tags_overview_{lim}_{('all' if not q else q)}.csv",
    type="secondary",
    mime="text/csv",
)