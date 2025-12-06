# carp_app/ui/pages/230_🔎_overview_clutches_flat.py
from __future__ import annotations

import sys
import pathlib
from datetime import datetime
from typing import Optional, Dict, Any, List

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
except Exception:
    def require_app_unlock() -> None:
        ...
from carp_app.ui.lib.page_engine import engine as _engine

# ───────── auth & page ─────────
sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(
    page_title="CARP — 🔎 Flat overview: clutches × treatments × selections",
    page_icon="🔎",
    layout="wide",
)
st.title("🔎 Flat overview — clutches × treated clutches × selections")


# ───────── engine ─────────
def eng() -> Engine:
    return _engine()


def _norm(s: str | None) -> Optional[str]:
    s = (s or "").strip()
    return s or None


# ───────── loader ─────────
@st.cache_data(show_spinner=False)
def load_flat_clutch_treated_selected(
    q: Optional[str],
    from_date: Optional[str],
    to_date: Optional[str],
    limit: int,
) -> pd.DataFrame:
    """
    Flat overview of clutches with treated clutches and selections.

    Three levels:
      • level = 'clutch'         → base clutch row
      • level = 'treated_clutch' → one per treated_clutches_v11
      • level = 'selection'      → one per selection event
    """
    sql = text(
        """
        WITH base_clutches AS (
          SELECT
            c.id::uuid          AS clutch_id,
            c.clutch_code,
            c.clutch_date
          FROM public.clutches c
          WHERE COALESCE(c.source_system, '') <> 'legacy_imaging'
        ),
        treated AS (
          SELECT
            tc.id::uuid         AS treated_clutch_id,
            tc.clutch_id::uuid  AS clutch_id,
            tc.treated_clutch_code,
            t.treat_code        AS treatment_code,
            t.treat_text
          FROM public.treated_clutches_v11 tc
          LEFT JOIN public.treatments t
            ON t.id = tc.treatment_id
        ),
        sel AS (
          SELECT
            cs.selection_event_id::uuid AS selection_event_id,
            cs.selection_kind,
            cs.selection_label,
            cs.is_primary,
            cs.clutch_id::uuid          AS clutch_id,
            cs.treated_clutch_id::uuid  AS treated_clutch_id,
            cs.genotype_code,
            cs.genotype_basecodes,
            cs.genotype_pretty
          FROM public.v11_clutch_selection_star cs
        ),

        clutch_rows AS (
          SELECT
            'clutch'                    AS level,
            bc.clutch_id::text          AS clutch_id,
            bc.clutch_code,
            bc.clutch_date,
            NULL::text                  AS treated_clutch_id,
            NULL::text                  AS treated_clutch_code,
            NULL::text                  AS treatment_code,
            NULL::text                  AS treat_text,
            NULL::text                  AS selection_event_id,
            NULL::text                  AS selection_kind,
            NULL::text                  AS selection_label,
            NULL::boolean               AS is_primary,
            NULL::text                  AS genotype_code,
            NULL::text                  AS genotype_basecodes,
            NULL::text                  AS genotype_pretty
          FROM base_clutches bc
        ),

        treated_rows AS (
          SELECT
            'treated_clutch'            AS level,
            bc.clutch_id::text          AS clutch_id,
            bc.clutch_code,
            bc.clutch_date,
            tr.treated_clutch_id::text  AS treated_clutch_id,
            tr.treated_clutch_code,
            tr.treatment_code,
            tr.treat_text,
            NULL::text                  AS selection_event_id,
            NULL::text                  AS selection_kind,
            NULL::text                  AS selection_label,
            NULL::boolean               AS is_primary,
            NULL::text                  AS genotype_code,
            NULL::text                  AS genotype_basecodes,
            NULL::text                  AS genotype_pretty
          FROM base_clutches bc
          JOIN treated tr
            ON tr.clutch_id = bc.clutch_id
        ),

        selection_rows AS (
          SELECT
            'selection'                 AS level,
            bc.clutch_id::text          AS clutch_id,
            bc.clutch_code,
            bc.clutch_date,
            tr.treated_clutch_id::text  AS treated_clutch_id,
            tr.treated_clutch_code,
            tr.treatment_code,
            tr.treat_text,
            s.selection_event_id::text  AS selection_event_id,
            s.selection_kind,
            s.selection_label,
            s.is_primary,
            s.genotype_code,
            s.genotype_basecodes,
            s.genotype_pretty
          FROM base_clutches bc
          LEFT JOIN treated tr
            ON tr.clutch_id = bc.clutch_id
          JOIN sel s
            ON s.clutch_id = bc.clutch_id
           AND (tr.treated_clutch_id IS NULL OR s.treated_clutch_id = tr.treated_clutch_id)
        ),

        all_rows AS (
          SELECT * FROM clutch_rows
          UNION ALL
          SELECT * FROM treated_rows
          UNION ALL
          SELECT * FROM selection_rows
        )

        SELECT *
        FROM all_rows
        WHERE (
               :q IS NULL
            OR clutch_code                    ILIKE :ql
            OR COALESCE(treated_clutch_code,'') ILIKE :ql
            OR COALESCE(treatment_code,'')      ILIKE :ql
            OR COALESCE(treat_text,'')          ILIKE :ql
            OR COALESCE(selection_label,'')     ILIKE :ql
            OR COALESCE(genotype_pretty,'')     ILIKE :ql
        )
        AND (:from_d IS NULL OR clutch_date >= :from_d)
        AND (:to_d   IS NULL OR clutch_date <= :to_d)
        ORDER BY clutch_date DESC NULLS LAST,
                 clutch_code,
                 level,
                 treated_clutch_code NULLS FIRST,
                 selection_label NULLS FIRST
        LIMIT :lim;
        """
    )
    params = {
        "q": q,
        "ql": f"%{q}%" if q else None,
        "from_d": from_date,
        "to_d": to_date,
        "lim": int(limit),
    }
    with eng().begin() as cx:
        df = pd.read_sql(sql, cx, params=params)
    return df.fillna("")


# ───────── filters ─────────
with st.form("flat_clutch_filters", clear_on_submit=False):
    c1, c2, c3, c4 = st.columns([3, 1.5, 1.5, 1])
    with c1:
        q_raw = st.text_input(
            "Search (clutch / treated clutch / treatment / selection / genotype)",
            "",
        )
    with c2:
        from_raw = st.text_input("From clutch_date (YYYY-MM-DD)", "")
    with c3:
        to_raw = st.text_input("To clutch_date (YYYY-MM-DD)", "")
    with c4:
        lim = int(
            st.number_input(
                "Limit",
                min_value=10,
                max_value=5000,
                value=500,
                step=50,
            )
        )
    _ = st.form_submit_button("Apply")

q = _norm(q_raw)
from_d: Optional[str] = None
to_d: Optional[str] = None

if from_raw:
    try:
        datetime.strptime(from_raw, "%Y-%m-%d")
        from_d = from_raw
    except ValueError:
        st.warning("From date must be YYYY-MM-DD if provided.")
if to_raw:
    try:
        datetime.strptime(to_raw, "%Y-%m-%d")
        to_d = to_raw
    except ValueError:
        st.warning("To date must be YYYY-MM-DD if provided.")

flat_df = load_flat_clutch_treated_selected(q, from_d, to_d, lim)

if flat_df.empty:
    st.info("No clutches / treated clutches / selections match the current filters.")
    st.stop()

st.caption(f"{len(flat_df)} flat row(s) (clutch × treated_clutch × selection)")

# ───────── main flat table ─────────

view_cols = [
    "level",
    "clutch_code",
    "clutch_date",
    "treated_clutch_code",
    "treatment_code",
    "treat_text",
    "selection_label",
    "selection_kind",
    "is_primary",
    "genotype_code",
    "genotype_basecodes",
    "genotype_pretty",
]
view_cols = [c for c in view_cols if c in flat_df.columns]

flat_view = flat_df[view_cols].copy()

st.data_editor(
    flat_view,
    key="flat_clutches_treatments_selections_v11",
    hide_index=True,
    use_container_width=True,
    num_rows="fixed",
    column_config={
        "level": st.column_config.TextColumn("Level", disabled=True),
        "clutch_code": st.column_config.TextColumn("Clutch", disabled=True),
        "clutch_date": st.column_config.DateColumn("Clutch date", disabled=True),
        "treated_clutch_code": st.column_config.TextColumn("Treated clutch", disabled=True),
        "treatment_code": st.column_config.TextColumn("Treatment code", disabled=True),
        "treat_text": st.column_config.TextColumn("Treatment text", disabled=True, width="large"),
        "selection_label": st.column_config.TextColumn("Selection label", disabled=True, width="large"),
        "selection_kind": st.column_config.TextColumn("Selection kind", disabled=True),
        "is_primary": st.column_config.CheckboxColumn("Primary?", disabled=True),
        "genotype_code": st.column_config.TextColumn("Genotype code", disabled=True),
        "genotype_basecodes": st.column_config.TextColumn("Genotype basecodes", disabled=True, width="large"),
        "genotype_pretty": st.column_config.TextColumn("Genotype pretty", disabled=True, width="large"),
    },
)

csv_flat = flat_view.to_csv(index=False).encode("utf-8")
st.download_button(
    "⬇︎ Download flat clutch × treatment × selection rows (CSV)",
    data=csv_flat,
    file_name="clutches_treated_selections_flat_v11.csv",
    type="secondary",
    mime="text/csv",
)