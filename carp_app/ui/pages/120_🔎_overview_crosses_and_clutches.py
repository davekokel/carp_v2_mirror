from __future__ import annotations

import sys
import pathlib
from datetime import datetime, date
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
from carp_app.ui.lib.page_engine import engine as _engine  # core hook


# ───────── auth & page ─────────
sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(
    page_title="CARP — Overview: Crosses & clutches",
    page_icon="🔎",
    layout="wide",
)
st.title("🔎 Overview: Crosses & clutches")


def eng() -> Engine:
    return _engine()


def _norm(s: str | None) -> Optional[str]:
    s = (s or "").strip()
    return s or None


# ════════════════════════════════════════════════════════
# FILTER BAR
# ════════════════════════════════════════════════════════
with st.form("cross_clutch_filters", clear_on_submit=False):
    c1, c2, c3, c4 = st.columns([3, 1.3, 1.3, 0.7])
    with c1:
        q_raw = st.text_input(
            "Search (TP-000001, FISH-2025-0001, tank pair, cross code, clutch code, fish)",
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
    _ = st.form_submit_button("Apply", key="cross_clutch_apply")

q = _norm(q_raw)
from_date: Optional[date] = None
to_date: Optional[date] = None

if from_raw:
    try:
        from_date = datetime.strptime(from_raw, "%Y-%m-%d").date()
    except ValueError:
        st.warning("From date must be YYYY-MM-DD if provided.")
        st.stop()

if to_raw:
    try:
        to_date = datetime.strptime(to_raw, "%Y-%m-%d").date()
    except ValueError:
        st.warning("To date must be YYYY-MM-DD if provided.")
        st.stop()

# ════════════════════════════════════════════════════════
# MAIN QUERY: clutches + crosses + v11_clutch_star
# ════════════════════════════════════════════════════════
where: List[str] = ["1=1"]
params: Dict[str, Any] = {"lim": lim}

if q:
    params["ql"] = f"%{q}%"
    where.append(
        "("
        " clutch_code         ILIKE :ql"
        " OR clutch_label     ILIKE :ql"
        " OR cross_code       ILIKE :ql"
        " OR cross_id::text   ILIKE :ql"
        " OR cross_date::text ILIKE :ql"
        " OR female_fish_code ILIKE :ql"
        " OR male_fish_code   ILIKE :ql"
        " OR tank_pair_code   ILIKE :ql"
        ")"
    )

if from_date:
    params["from_d"] = from_date.isoformat()
    where.append("clutch_date >= :from_d")

if to_date:
    params["to_d"] = to_date.isoformat()
    where.append("clutch_date <= :to_d")

where_sql = " AND ".join(where)

sql = text(
    f"""
    WITH crows AS (
      SELECT
        c.id               AS clutch_id,
        c.clutch_code,
        c.clutch_date,
        c.estimated_egg_count,
        c.notes,
        c.source_system,
        c.import_batch_id,
        c.created_at,
        cr.id              AS cross_id,
        cr.cross_run_code  AS cross_code,
        cr.created_at      AS cross_date,
        tp.tank_pair_code  AS tank_pair_code,
        ff.fish_code       AS female_fish_code,
        mf.fish_code       AS male_fish_code
      FROM public.clutches c
      LEFT JOIN public.crosses cr
        ON cr.id = c.cross_id
      LEFT JOIN public.tank_pairs tp
        ON tp.id = cr.tank_pair_id
      LEFT JOIN public.fish_instances_v10 ff
        ON ff.id = cr.female_fish_id
      LEFT JOIN public.fish_instances_v10 mf
        ON mf.id = cr.male_fish_id
      WHERE
        (c.source_system IS NULL OR c.source_system <> 'legacy')
        AND (c.import_batch_id IS NULL OR c.import_batch_id NOT LIKE 'legacy_%')
    )
    SELECT
      c.clutch_id::text                                  AS clutch_id,
      c.clutch_code,
      ('CL-' || right(c.clutch_code, 8))                 AS clutch_label,
      c.clutch_date,
      c.estimated_egg_count,
      c.cross_id::text                                   AS cross_id,
      c.cross_date,
      c.cross_code,
      c.tank_pair_code,
      cs.genotype_base_codes                             AS genotype_base_codes,
      cs.genotype_v11_code                               AS genotype_v11_code,
      cs.genotype_v11_basecodes                          AS genotype_v11_basecodes,
      cs.treat_codes                                     AS treat_codes,
      cs.treat_basecodes                                 AS treat_basecodes,
      c.female_fish_code,
      c.male_fish_code,
      c.notes,
      c.source_system,
      c.import_batch_id,
      c.created_at
    FROM crows c
    LEFT JOIN public.v11_clutch_star cs
      ON cs.clutch_id = c.clutch_id
    WHERE {where_sql}
    ORDER BY c.cross_date DESC NULLS LAST,
             c.clutch_date DESC NULLS LAST,
             c.created_at DESC NULLS LAST
    LIMIT :lim;
"""
)

with eng().begin() as cx:
    df = pd.read_sql(sql, cx, params=params)

# convert tz if needed
for col in ["cross_date", "created_at"]:
    if col in df.columns and pd.api.types.is_datetime64tz_dtype(df[col].dtype):
        df[col] = df[col].dt.tz_convert("America/Los_Angeles")

df = df.fillna("")
st.caption(f"{len(df)} clutch instance(s) / cross row(s)")

if df.empty:
    st.info("No clutches / crosses match the current filters.")
    st.stop()

# derive parent_cross_pretty for display
df["parent_cross_pretty"] = df.apply(
    lambda r: f"{r['female_fish_code']} × {r['male_fish_code']}"
    if r["female_fish_code"] or r["male_fish_code"]
    else "",
    axis=1,
)

# ════════════════════════════════════════════════════════
# MAIN OVERVIEW TABLE (core-ish clutch summary)
# ════════════════════════════════════════════════════════
st.subheader("Overview", anchor=False)

view = df.copy()
view.insert(0, "✓ Select", False)

overview_cols = [
    "✓ Select",
    "clutch_code",
    "clutch_date",
    "cross_code",
    "cross_date",
    "tank_pair_code",
    "parent_cross_pretty",
    "genotype_v11_code",
    "treat_codes",
    "treat_basecodes",
]
overview_cols = [c for c in overview_cols if c in view.columns]

grid = st.data_editor(
    view[overview_cols],
    key="crosses_clutches_overview_v11_core",
    hide_index=True,
    use_container_width=True,
    num_rows="fixed",
)

sel = grid.loc[grid["✓ Select"] == True] if "✓ Select" in grid.columns else pd.DataFrame()

# ════════════════════════════════════════════════════════
# DRILL-DOWN: SELECTED CLUTCH / CROSS
# ════════════════════════════════════════════════════════
st.subheader("Selected cross & clutch — details", anchor=False)

if sel.empty:
    st.caption("Select a single row above to see detailed fields and expected genotypes.")
else:
    clutch_id_sel = sel.iloc[0]["clutch_code"]
    # Use clutch_code as key back into df (clutch_id is also available if needed)
    full_row = df[df["clutch_code"] == clutch_id_sel].iloc[0]

    detail_cols = [
        "clutch_id",
        "clutch_code",
        "clutch_label",
        "clutch_date",
        "estimated_egg_count",
        "cross_id",
        "cross_code",
        "cross_date",
        "tank_pair_code",
        "parent_cross_pretty",
        "genotype_base_codes",
        "genotype_v11_code",
        "genotype_v11_basecodes",
        "treat_codes",
        "treat_basecodes",
        "female_fish_code",
        "male_fish_code",
        "notes",
        "source_system",
        "import_batch_id",
        "created_at",
    ]
    detail_cols = [c for c in detail_cols if c in df.columns]

    detail_series = full_row[detail_cols]
    detail_df = detail_series.reset_index()
    detail_df.columns = ["Field", "Value"]

    tab1, tab2 = st.tabs(["Clutch / cross fields", "Expected genotypes"])

    with tab1:
        st.dataframe(
            detail_df,
            use_container_width=True,
            height=min(800, 30 * len(detail_df)),
        )

    with tab2:
        # Expected-genotype rows for this clutch (core clutch fields: treatments & rollups)
        exp_sql = text(
            """
            SELECT
              label,
              genotype_basecode_code,
              genotype_transgene_allele_code,
              treatments_and_transgenes,
              all_fluor_tag_rollup,
              all_organelle_fluor_rollup
            FROM public.clutch_expected_genotypes_v11
            WHERE clutch_id = :cid
            ORDER BY label;
            """
        )
        with eng().begin() as cx:
            df_exp = pd.read_sql(exp_sql, cx, params={"cid": full_row["clutch_id"]})

        if df_exp.empty:
            st.caption("No expected-genotype rows recorded for this clutch.")
        else:
            df_exp = df_exp.fillna("")

            # These columns align with your clutch core field design:
            # treatments_and_transgenes, all_fluor_tag_rollup, all_organelle_fluor_rollup
            st.dataframe(
                df_exp[
                    [
                        "label",
                        "genotype_basecode_code",
                        "genotype_transgene_allele_code",
                        "treatments_and_transgenes",
                        "all_fluor_tag_rollup",
                        "all_organelle_fluor_rollup",
                    ]
                ],
                use_container_width=True,
            )

# ════════════════════════════════════════════════════════
# EXPORT
# ════════════════════════════════════════════════════════
st.download_button(
    "⬇︎ Download cross & clutch rows (CSV)",
    data=df.to_csv(index=False).encode("utf-8"),
    file_name="crosses_clutches_overview_v11.csv",
    type="secondary",
    mime="text/csv",
)