from __future__ import annotations

import pathlib
import sys
from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st
from sqlalchemy import text
from sqlalchemy.engine import Engine

# ───────── repo bootstrap ─────────
ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from carp_app.ui.auth_gate import require_auth
from carp_app.ui.email_otp_gate import require_email_otp
try:
    from carp_app.ui.auth_gate import require_app_unlock
except Exception:  # staging / local compatibility
    def require_app_unlock() -> None:
        ...
from carp_app.ui.lib.app_ctx import get_engine

# ───────── auth & page ─────────
sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(
    page_title="CARP — Overview: Transgenes & Alleles",
    page_icon="🔎",
    layout="wide",
)
st.title("🔎 Overview: Transgenes & Alleles")


@st.cache_resource(show_spinner=False)
def eng() -> Engine:
    return get_engine()


def _norm(s: Optional[str]) -> Optional[str]:
    s = (s or "").strip()
    return s or None


# ────────────────────────────────────────────────────────
# Loaders
# ────────────────────────────────────────────────────────

@st.cache_data(show_spinner=False)
def load_transgenes(q: Optional[str], limit: int) -> pd.DataFrame:
    """
    Load transgenes from public.transgenes with a simple text filter.
    Backed by public.v_transgenes_overview where possible.
    """
    where: List[str] = ["1=1"]
    params: Dict[str, Any] = {"lim": int(limit)}

    if q:
        params["ql"] = f"%{q}%"
        where.append(
            "("
            "  transgene_base_code ILIKE :ql"
            " OR COALESCE(construct_code,'') ILIKE :ql"
            " OR COALESCE(construct_name,'') ILIKE :ql"
            " OR COALESCE(description,'') ILIKE :ql"
            ")"
        )

    sql = text(
        f"""
        SELECT
          transgene_base_code AS base_code,
          construct_code,
          construct_name       AS name,
          description,
          n_alleles,
          marker_basecode_style,
          marker_fluortag_style,
          marker_organelle_style
        FROM public.v_transgenes_overview
        WHERE {" AND ".join(where)}
        ORDER BY transgene_base_code
        LIMIT :lim;
        """
    )

    with eng().begin() as cx:
        df = pd.read_sql(sql, cx, params=params)

    for c in df.select_dtypes(include=["object", "string"]).columns:
        df[c] = df[c].astype("string").fillna("")
    return df


@st.cache_data(show_spinner=False)
def load_alleles_for_transgene(base_code: str) -> pd.DataFrame:
    """
    Load alleles for a given transgene_base_code.
    """
    sql = text(
        """
        SELECT
          transgene_base_code   AS base_code,
          allele_number,
          allele_name,
          allele_nickname,
          COALESCE(notes,'')    AS notes
        FROM public.transgene_alleles
        WHERE transgene_base_code = :bc
        ORDER BY allele_number;
        """
    )
    with eng().begin() as cx:
        df = pd.read_sql(sql, cx, params={"bc": base_code})

    for c in df.select_dtypes(include=["object", "string"]).columns:
        df[c] = df[c].astype("string").fillna("")
    return df


# ────────────────────────────────────────────────────────
# Filters
# ────────────────────────────────────────────────────────

with st.form("transgene_filters", clear_on_submit=False):
    c1, c2 = st.columns([3, 1])
    with c1:
        q_raw = st.text_input(
            "Search (base_code / name / description)",
            "",
            key="transgene_search_text",
        )
    with c2:
        limit = int(
            st.number_input(
                "Limit (transgenes)",
                min_value=10,
                max_value=5000,
                value=1000,
                step=50,
                key="transgene_limit",
            )
        )
    _ = st.form_submit_button("Apply")

q = _norm(q_raw)

# ────────────────────────────────────────────────────────
# Step 1 — Transgene table (select via checkbox)
# ────────────────────────────────────────────────────────

st.subheader("Transgenes", anchor=False)

tg_df = load_transgenes(q, limit)

if tg_df.empty:
    st.info("No transgenes match these filters.")
    st.stop()

st.caption(f"{len(tg_df)} transgene(s)")

tg_view = tg_df.copy()
tg_view.insert(0, "✓ Select", False)

display_cols = [
    "✓ Select",
    "base_code",
    "name",
    "construct_code",
    "n_alleles",
    "marker_basecode_style",
    "marker_fluortag_style",
    "marker_organelle_style",
]
display_cols = [c for c in display_cols if c in tg_view.columns]
tg_display = tg_view[display_cols]

tg_grid = st.data_editor(
    tg_display,
    key="transgenes_overview_grid",
    hide_index=True,
    use_container_width=True,
    num_rows="fixed",
    column_config={
        "✓ Select": st.column_config.CheckboxColumn("✓", default=False),
        "base_code": st.column_config.TextColumn("Base code", disabled=True),
        "name": st.column_config.TextColumn("Name", disabled=True, width="large"),
        "construct_code": st.column_config.TextColumn(
            "Construct code", disabled=True
        ),
        "n_alleles": st.column_config.NumberColumn(
            "# alleles", disabled=True, format="%d"
        ),
        "marker_basecode_style": st.column_config.TextColumn(
            "Markers — basecode style", disabled=True, width="large"
        ),
        "marker_fluortag_style": st.column_config.TextColumn(
            "Markers — fluor::tag(tag_pos)", disabled=True, width="large"
        ),
        "marker_organelle_style": st.column_config.TextColumn(
            "Markers — organelle–fluor", disabled=True, width="large"
        ),
    },
)

sel_mask = (
    tg_grid.get("✓ Select", pd.Series(False, index=tg_grid.index))
    .fillna(False)
    .astype(bool)
)

if not sel_mask.any():
    st.caption(
        "No transgene selected — check a row above to see allele details."
    )
    st.stop()

sel_idx = tg_grid.index[sel_mask].tolist()[0]
selected_base_code = tg_grid.loc[sel_idx, "base_code"]

st.markdown("---")

# ────────────────────────────────────────────────────────
# Step 2 — Alleles for selected transgene
# ────────────────────────────────────────────────────────

st.subheader("Alleles for selected transgene", anchor=False)
st.caption(f"Selected transgene: **{selected_base_code}**")

alleles_df = load_alleles_for_transgene(selected_base_code)

if alleles_df.empty:
    st.info("No alleles defined for this transgene yet.")
else:
    alleles_view = alleles_df[
        ["allele_number", "allele_name", "allele_nickname", "notes"]
    ].copy()
    alleles_view.rename(
        columns={
            "allele_number": "Allele #",
            "allele_name": "Allele name",
            "allele_nickname": "Nickname",
            "notes": "Notes",
        },
        inplace=True,
    )
    st.data_editor(
        alleles_view,
        key="alleles_for_transgene",
        hide_index=True,
        use_container_width=True,
        num_rows="fixed",
        column_config={
            "Allele #": st.column_config.NumberColumn("Allele #", disabled=True),
            "Allele name": st.column_config.TextColumn(
                "Allele name", disabled=True, width="large"
            ),
            "Nickname": st.column_config.TextColumn(
                "Nickname", disabled=True, width="medium"
            ),
            "Notes": st.column_config.TextColumn(
                "Notes", disabled=True, width="stretch"
            ),
        },
    )