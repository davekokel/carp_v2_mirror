from __future__ import annotations

import sys
import os
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
    def require_app_unlock():
        ...
from carp_app.ui.lib.page_engine import engine as _engine

# ───────── auth & page ─────────
sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(
    page_title="CARP — Overview crosses & clutches",
    page_icon="🔎",
    layout="wide",
)
st.title("🔎 Overview crosses & clutches")


# ───────── engine ─────────
def eng() -> Engine:
    return _engine()


def _norm(s: str | None) -> Optional[str]:
    s = (s or "").strip()
    return s or None


# ───────── loaders ─────────
@st.cache_data(show_spinner=False)
def load_cross_clutch_rows(
    q: Optional[str],
    from_date: Optional[str],
    to_date: Optional[str],
    limit: int,
) -> pd.DataFrame:
    """
    Combined cross + clutch overview using clutches + crosses + tank_pairs + fish_instances_v10 + v11_clutch_star.
    """
    sql = text(
        """
        WITH base AS (
          SELECT
            c.id::uuid                AS clutch_id,
            c.clutch_code,
            c.clutch_date,
            c.estimated_egg_count,
            cr.id::uuid               AS cross_id,
            cr.cross_run_code         AS cross_code,
            cr.cross_date,
            tp.tank_pair_code,
            mom.fish_code             AS female_fish_code,
            dad.fish_code             AS male_fish_code
          FROM public.clutches c
          LEFT JOIN public.crosses cr
            ON cr.id = c.cross_id
          LEFT JOIN public.tank_pairs tp
            ON tp.id = cr.tank_pair_id
          LEFT JOIN public.fish_instances_v10 mom
            ON mom.id = cr.female_fish_id
          LEFT JOIN public.fish_instances_v10 dad
            ON dad.id = cr.male_fish_id
        )
        SELECT
          b.clutch_id::text                    AS clutch_id,
          b.clutch_code,
          ('CL-' || b.clutch_code)             AS clutch_label,
          b.clutch_date,
          b.estimated_egg_count,
          b.cross_id::text                     AS cross_id,
          b.cross_code,
          b.cross_date,
          b.tank_pair_code,
          COALESCE(b.female_fish_code, '') || ' × ' || COALESCE(b.male_fish_code, '') AS parent_cross_pretty,
          cs.genotype_base_codes,
          cs.genotype_v11_code,
          cs.genotype_v11_basecodes,
          cs.genotype_pretty,
          cs.treat_codes,
          cs.treat_basecodes,
          b.female_fish_code,
          b.male_fish_code
        FROM base b
        LEFT JOIN public.v11_clutch_star cs
          ON cs.clutch_id = b.clutch_id
        WHERE (
               :q IS NULL
            OR b.clutch_code     ILIKE :ql
            OR b.cross_code      ILIKE :ql
            OR b.tank_pair_code  ILIKE :ql
            OR COALESCE(b.female_fish_code, '') ILIKE :ql
            OR COALESCE(b.male_fish_code, '')   ILIKE :ql
        )
        AND (:from_d IS NULL OR b.clutch_date >= :from_d)
        AND (:to_d   IS NULL OR b.clutch_date <= :to_d)
        ORDER BY b.clutch_date DESC NULLS LAST, b.clutch_code
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


@st.cache_data(show_spinner=False)
def load_expected_genotypes(clutch_id: str) -> pd.DataFrame:
    sql = text(
        """
        SELECT
          id::text                     AS id,
          label,
          treatment_code,
          genotype_basecode_code       AS genotype_basecodes,
          genotype_transgene_allele_code AS genotype_alleles,
          treatments_and_transgenes,
          all_fluor_tag_rollup,
          all_organelle_fluor_rollup,
          expected_fraction,
          expected_percent_label,
          is_enabled,
          notes,
          created_at,
          created_by
        FROM public.clutch_expected_genotypes_v11
        WHERE clutch_id = :cid
        ORDER BY label;
        """
    )
    with eng().begin() as cx:
        df = pd.read_sql(sql, cx, params={"cid": clutch_id})
    return df.fillna("")


@st.cache_data(show_spinner=False)
def load_treatment_overview() -> pd.DataFrame:
    """
    Global treatment overview from v11_treatment_star + mix counts.
    Reused for per-clutch treatment summary (filtered by codes).
    """
    sql = text(
        """
        WITH mix_counts AS (
          SELECT
            tm.treatment_id,
            COUNT(DISTINCT tmc.construct_id) AS n_constructs,
            COUNT(DISTINCT tmd.dye_id)       AS n_dyes
          FROM public.treatment_mixes tm
          LEFT JOIN public.treatment_mix_constructs tmc
            ON tmc.mix_id = tm.id
          LEFT JOIN public.treatment_mix_dyes tmd
            ON tmd.mix_id = tm.id
          GROUP BY tm.treatment_id
        )
        SELECT
          ts.treatment_id,
          ts.treatment_code,
          ts.kind_code,
          ts.treat_text,
          COALESCE(mc.n_constructs, 0)       AS n_constructs,
          COALESCE(mc.n_dyes, 0)             AS n_dyes,
          ts.genotype_basecode_code,
          ts.materials_by_kind,
          ts.all_fluor_tag_rollup,
          ts.all_organelle_fluor_rollup
        FROM public.v11_treatment_star ts
        LEFT JOIN mix_counts mc
          ON mc.treatment_id::text = ts.treatment_id
        ORDER BY ts.treatment_code;
        """
    )
    with eng().begin() as cx:
        df = pd.read_sql(sql, cx)
    return df.fillna("")


# ───────── filters ─────────
with st.form("cross_clutch_filters", clear_on_submit=False):
    c1, c2, c3, c4 = st.columns([3, 1.5, 1.5, 1])
    with c1:
        q_raw = st.text_input(
            "Search (clutch / cross / tank pair / parent FSH)",
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
                max_value=2000,
                value=200,
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

rows = load_cross_clutch_rows(q, from_d, to_d, lim)

if rows.empty:
    st.info("No cross / clutch rows match the current filters.")
    st.stop()

st.subheader("Step 1 — Select a cross + clutch row", anchor=False)

# build a user-facing view WITHOUT the raw IDs
view = rows.copy()
view.insert(0, "✓ Select", False)

visible_cols = [
    "✓ Select",
    "clutch_code",
    "clutch_label",
    "clutch_date",
    "estimated_egg_count",
    "cross_code",
    "cross_date",
    "tank_pair_code",
    "female_fish_code",
    "male_fish_code",
    "genotype_v11_basecodes",
    "genotype_pretty",
    "treat_codes",
    "treat_basecodes",
]
visible_cols = [c for c in visible_cols if c in view.columns]

grid = st.data_editor(
    view[visible_cols],
    key="cross_clutch_overview_grid_v11",
    hide_index=True,
    width="stretch",
    num_rows="fixed",
)

sel_mask = grid["✓ Select"] == True if "✓ Select" in grid.columns else pd.Series(False, index=grid.index)
selected_idx = sel_mask.index[sel_mask]

if selected_idx.empty:
    st.info("Select one row above to see details.")
    st.stop()

row = rows.loc[selected_idx].iloc[0]

st.subheader("Selected cross & clutch — details", anchor=False)

tab_fields, tab_genotypes, tab_treatments = st.tabs(["Clutch / cross fields", "Expected genotypes", "Treatments"])

# ───────── Tab 1 — clutch / cross fields ─────────
with tab_fields:
    fields: Dict[str, Any] = {
        "clutch_id": row.get("clutch_id"),
        "clutch_code": row.get("clutch_code"),
        "clutch_label": row.get("clutch_label"),
        "clutch_date": row.get("clutch_date"),
        "estimated_egg_count": row.get("estimated_egg_count"),
        "cross_id": row.get("cross_id"),
        "cross_code": row.get("cross_code"),
        "cross_date": row.get("cross_date"),
        "tank_pair_code": row.get("tank_pair_code"),
        "parent_cross_pretty": row.get("parent_cross_pretty"),
        "genotype_base_codes": row.get("genotype_base_codes"),
        "genotype_v11_code": row.get("genotype_v11_code"),
        "genotype_v11_basecodes": row.get("genotype_v11_basecodes"),
        "treat_codes": row.get("treat_codes"),
        "treat_basecodes": row.get("treat_basecodes"),
        "female_fish_code": row.get("female_fish_code"),
        "male_fish_code": row.get("male_fish_code"),
    }

    fields_df = pd.DataFrame(
        [{"Field": k, "Value": "" if v is None else str(v)} for k, v in fields.items()]
    )

    st.dataframe(
        fields_df,
        hide_index=True,
        width="stretch",
    )

    csv_fields = fields_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "⬇︎ Download cross & clutch rows (CSV)",
        data=csv_fields,
        file_name=f"{row.get('clutch_code','clutch')}_cross_clutch_fields.csv",
        type="secondary",
        mime="text/csv",
    )

# ───────── Tab 2 — expected genotypes ─────────
with tab_genotypes:
    clutch_uuid = row["clutch_id"]
    eg = load_expected_genotypes(clutch_uuid)

    if eg.empty:
        st.info("No expected-genotype rows for this clutch.")
    else:
        # show the full expected-genotypes (including treatments_and_transgenes) here
        st.dataframe(
            eg,
            hide_index=True,
            width="stretch",
        )

        csv_eg = eg.to_csv(index=False).encode("utf-8")
        st.download_button(
            "⬇︎ Download expected-genotypes (CSV)",
            data=csv_eg,
            file_name=f"{row.get('clutch_code','clutch')}_expected_genotypes_v11.csv",
            type="secondary",
            mime="text/csv",
        )

# ───────── Tab 3 — treatments ─────────
with tab_treatments:
    st.markdown("### Clutch-level treatments (from expected genotypes)")

    clutch_uuid = row["clutch_id"]
    eg = load_expected_genotypes(clutch_uuid)

    # distinct non-empty treatment codes from expected-genotype rows
    codes: List[str] = []
    if not eg.empty and "treatment_code" in eg.columns:
        codes = sorted(
            set(
                s
                for s in eg["treatment_code"].astype(str).str.strip().tolist()
                if s and s.lower() != "none"
            )
        )

    if not codes:
        st.info("No treatments recorded for this clutch in expected-genotype rows.")
    else:
        all_treats = load_treatment_overview()
        tcl = all_treats[all_treats["treatment_code"].isin(codes)].copy()

        if tcl.empty:
            st.info("No matching treatments found in v11_treatment_star for these codes.")
        else:
            st.dataframe(
                tcl[
                    [
                        "treatment_code",
                        "kind_code",
                        "treat_text",
                        "genotype_basecode_code",
                        "materials_by_kind",
                        "n_constructs",
                        "n_dyes",
                        "all_fluor_tag_rollup",
                        "all_organelle_fluor_rollup",
                    ]
                ],
                hide_index=True,
                width="stretch",
            )
            csv_tcl = tcl.to_csv(index=False).encode("utf-8")
            st.download_button(
                "⬇︎ Download clutch-level treatments (CSV)",
                data=csv_tcl,
                file_name=f"{row.get('clutch_code','clutch')}_clutch_treatments_from_expected.csv",
                type="secondary",
                mime="text/csv",
            )

    st.markdown("### Genotype-level treatments (expected genotypes)")

    if eg.empty:
        st.info("No expected-genotype rows for this clutch.")
    else:
        # genotype-level view WITHOUT treatments_and_transgenes to avoid confusion
        cols_simple = ["label", "treatment_code", "is_enabled"]
        cols_simple = [c for c in cols_simple if c in eg.columns]
        eg_simple = eg[cols_simple].copy()

        st.dataframe(
            eg_simple,
            hide_index=True,
            width="stretch",
        )
        csv_eg_simple = eg_simple.to_csv(index=False).encode("utf-8")
        st.download_button(
            "⬇︎ Download genotype-level treatments (CSV)",
            data=csv_eg_simple,
            file_name=f"{row.get('clutch_code','clutch')}_genotype_treatments.csv",
            type="secondary",
            mime="text/csv",
        )