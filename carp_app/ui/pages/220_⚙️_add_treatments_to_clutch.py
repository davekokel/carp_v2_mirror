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
    page_title="CARP — ⚙️ Add treatments to clutch",
    page_icon="⚙️",
    layout="wide",
)
st.title("⚙️ Add treatments to clutch")


def eng() -> Engine:
    return _engine()


def _norm(s: str | None) -> Optional[str]:
    s = (s or "").strip()
    return s or None


# ════════════════════════════════════════════════════════
# SECTION 1 — FILTER + PICK CLUTCH
# ════════════════════════════════════════════════════════
st.subheader("Step 1 — Select a clutch", anchor=False)

with st.form("clutch_filters_for_treatments", clear_on_submit=False):
    c1, c2, c3, c4 = st.columns([3, 1.3, 1.3, 0.7])
    with c1:
        q_raw = st.text_input(
            "Search (clutch code / cross code / tank pair / parent fish)",
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
    _ = st.form_submit_button("Apply", key="clutch_filters_apply_treatments")

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

sql_clutches = text(
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
    df_clutches = pd.read_sql(sql_clutches, cx, params=params)

for col in ["cross_date", "created_at"]:
    if col in df_clutches.columns and pd.api.types.is_datetime64tz_dtype(
        df_clutches[col].dtype
    ):
        df_clutches[col] = df_clutches[col].dt.tz_convert("America/Los_Angeles")

df_clutches = df_clutches.fillna("")
st.caption(f"{len(df_clutches)} clutch row(s)")

if df_clutches.empty:
    st.info("No clutches match the current filters.")
    st.stop()

# parent cross pretty
df_clutches["parent_cross_pretty"] = df_clutches.apply(
    lambda r: f"{r['female_fish_code']} × {r['male_fish_code']}"
    if r["female_fish_code"] or r["male_fish_code"]
    else "",
    axis=1,
)

view = df_clutches.copy()
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

grid_clutches = st.data_editor(
    view[overview_cols],
    key="treatments_clutches_overview",
    hide_index=True,
    use_container_width=True,
    num_rows="fixed",
)

sel = (
    grid_clutches.loc[grid_clutches["✓ Select"] == True]
    if "✓ Select" in grid_clutches.columns
    else pd.DataFrame()
)

if sel.empty:
    st.info("Select a clutch above to edit its treatments.")
    st.stop()

sel_row = sel.iloc[0]
clutch_code = sel_row["clutch_code"]
clutch_row = df_clutches[df_clutches["clutch_code"] == clutch_code].iloc[0]
clutch_id = clutch_row["clutch_id"]

st.success(
    f"Selected clutch: {clutch_code} (cross {clutch_row['cross_code']}, "
    f"parents {clutch_row['parent_cross_pretty']})"
)

# ════════════════════════════════════════════════════════
# SECTION 2 — EDIT EXPECTED-GENOTYPE TREATMENTS
# ════════════════════════════════════════════════════════
st.subheader("Step 2 — Edit treatments for expected genotypes", anchor=False)

sql_exp = text(
    """
    SELECT
      id::text                           AS id,
      label,
      treatment_code,
      genotype_basecode_code,
      genotype_transgene_allele_code,
      treatments_and_transgenes,
      all_fluor_tag_rollup,
      all_organelle_fluor_rollup,
      expected_fraction,
      expected_percent_label,
      is_enabled,
      notes
    FROM public.clutch_expected_genotypes_v11
    WHERE clutch_id = :cid
    ORDER BY label;
    """
)

with eng().begin() as cx:
    df_exp_orig = pd.read_sql(sql_exp, cx, params={"cid": clutch_id})

df_exp_orig = df_exp_orig.fillna("")
st.caption(f"{len(df_exp_orig)} expected-genotype row(s) for this clutch")

if df_exp_orig.empty:
    st.info(
        "No expected-genotype rows recorded for this clutch yet. "
        "You can add them via the cross scheduling workflow."
    )
else:
    edit_view = df_exp_orig.copy()

    st.markdown(
        "You can edit the **treatment_code**, **treatments_and_transgenes**, "
        "**is_enabled**, and **notes** columns. Fluor/org rollups are derived."
    )

    edited = st.data_editor(
        edit_view,
        key="clutch_expected_genotypes_editor",
        hide_index=True,
        use_container_width=True,
        num_rows="fixed",
        column_config={
            "id": st.column_config.TextColumn("ID", disabled=True),
            "label": st.column_config.TextColumn("Label", disabled=True),
            "treatment_code": st.column_config.TextColumn(
                "Treatment code", disabled=False
            ),
            "genotype_basecode_code": st.column_config.TextColumn(
                "Genotype basecodes", disabled=True
            ),
            "genotype_transgene_allele_code": st.column_config.TextColumn(
                "Genotype alleles", disabled=True
            ),
            "treatments_and_transgenes": st.column_config.TextColumn(
                "Treatments > transgenes", disabled=False, width="large"
            ),
            "all_fluor_tag_rollup": st.column_config.TextColumn(
                "Fluor::tag rollup", disabled=True, width="large"
            ),
            "all_organelle_fluor_rollup": st.column_config.TextColumn(
                "Organelle-fluor rollup", disabled=True, width="large"
            ),
            "expected_fraction": st.column_config.NumberColumn(
                "Expected fraction", disabled=True
            ),
            "expected_percent_label": st.column_config.TextColumn(
                "% label", disabled=True
            ),
            "is_enabled": st.column_config.CheckboxColumn(
                "Enabled", default=True
            ),
            "notes": st.column_config.TextColumn(
                "Notes", disabled=False, width="large"
            ),
        },
    )

    if st.button("💾 Save treatments for this clutch", type="primary", use_container_width=True):
        try:
            update_sql = text(
                """
                UPDATE public.clutch_expected_genotypes_v11
                SET
                  treatment_code = :treatment_code,
                  treatments_and_transgenes = :treatments_and_transgenes,
                  is_enabled = :is_enabled,
                  notes = :notes
                WHERE id = :id::uuid;
                """
            )
            with eng().begin() as cx:
                for _, r in edited.iterrows():
                    cx.execute(
                        update_sql,
                        {
                            "id": r["id"],
                            "treatment_code": r.get("treatment_code") or None,
                            "treatments_and_transgenes": r.get(
                                "treatments_and_transgenes"
                            )
                            or None,
                            "is_enabled": bool(r.get("is_enabled", True)),
                            "notes": r.get("notes") or None,
                        },
                    )
            st.success("Treatments updated for all expected-genotype rows.")
        except Exception as e:
            st.error(f"Failed to update treatments: {type(e).__name__}: {e}")

    st.download_button(
        "⬇︎ Download expected-genotype table (CSV)",
        data=edited.to_csv(index=False).encode("utf-8"),
        file_name=f"clutch_expected_genotypes_{clutch_code}.csv",
        type="secondary",
        mime="text/csv",
    )