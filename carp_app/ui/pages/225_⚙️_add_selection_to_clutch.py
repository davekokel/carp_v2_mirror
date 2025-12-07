# carp_app/ui/pages/245_⚙️_manage_clutch_selections.py
# ⚙️ Manage clutch selections (v11) — central place to record genotype- and treatment-aware selections

from __future__ import annotations

import os
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
    def require_app_unlock():
        ...

from carp_app.ui.lib.page_engine import engine as _engine

# ───────── auth & page ─────────
sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(
    page_title="CARP — ⚙️ Manage clutch selections",
    page_icon="⚙️",
    layout="wide",
)
st.title("⚙️ Manage clutch selections (treatments • expected genotypes • phenotype picks)")


# ───────── engine / helpers ─────────
def eng() -> Engine:
    return _engine()


def _norm(s: str | None) -> Optional[str]:
    s = (s or "").strip()
    return s or None


def _who() -> str:
    return (
        getattr(user, "email", None)
        or os.getenv("USER")
        or os.getenv("USERNAME")
        or "system"
    )


# ───────── loaders ─────────
@st.cache_data(show_spinner=False)
def load_target_clutches_for_selection(
    q: Optional[str],
    from_date: Optional[str],
    to_date: Optional[str],
    limit: int,
) -> pd.DataFrame:
    """
    Flat target picker for selections.

    One row per:
      • level = 'clutch'         → base clutch
      • level = 'treated_clutch' → treated clutches under that clutch

    Each row carries n_selection_events for that (clutch, treated_clutch) pair.
    """
    sql = text(
        """
        WITH base AS (
          SELECT
            c.id::uuid                AS clutch_id,
            c.clutch_code,
            c.clutch_date,
            cr.id::uuid               AS cross_id,
            cr.cross_run_code         AS cross_code,
            cr.created_at::date       AS cross_date,
            cr.tank_pair_id::uuid     AS tank_pair_id,
            tp.tank_pair_code         AS tank_pair_code,
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
        sel_counts AS (
          SELECT
            clutch_id::uuid                    AS clutch_id,
            COALESCE(treated_clutch_id, NULL)  AS treated_clutch_id,
            COUNT(DISTINCT selection_event_id) AS n_selection_events
          FROM public.v11_clutch_selection_star
          GROUP BY clutch_id, treated_clutch_id
        ),

        clutch_targets AS (
          SELECT
            'clutch'                    AS level,
            b.clutch_id::text           AS clutch_id,
            NULL::text                  AS treated_clutch_id,
            b.clutch_code,
            b.clutch_date,
            NULL::text                  AS treated_clutch_code,
            NULL::text                  AS treatment_code,
            NULL::text                  AS treat_text,
            b.cross_code,
            b.cross_date,
            b.tank_pair_code,
            COALESCE(b.female_fish_code, '') || ' × ' || COALESCE(b.male_fish_code, '') AS parent_cross_pretty,
            COALESCE(sc.n_selection_events, 0) AS n_selection_events
          FROM base b
          LEFT JOIN sel_counts sc
            ON sc.clutch_id = b.clutch_id
           AND sc.treated_clutch_id IS NULL
        ),

        treated_targets AS (
          SELECT
            'treated_clutch'            AS level,
            b.clutch_id::text           AS clutch_id,
            tr.treated_clutch_id::text  AS treated_clutch_id,
            b.clutch_code,
            b.clutch_date,
            tr.treated_clutch_code,
            tr.treatment_code,
            tr.treat_text,
            b.cross_code,
            b.cross_date,
            b.tank_pair_code,
            COALESCE(b.female_fish_code, '') || ' × ' || COALESCE(b.male_fish_code, '') AS parent_cross_pretty,
            COALESCE(sc.n_selection_events, 0) AS n_selection_events
          FROM base b
          JOIN treated tr
            ON tr.clutch_id = b.clutch_id
          LEFT JOIN sel_counts sc
            ON sc.clutch_id = b.clutch_id
           AND sc.treated_clutch_id = tr.treated_clutch_id
        ),

        all_targets AS (
          SELECT * FROM clutch_targets
          UNION ALL
          SELECT * FROM treated_targets
        )
        SELECT *
        FROM all_targets
        WHERE (
               :q IS NULL
            OR clutch_code               ILIKE :ql
            OR COALESCE(treated_clutch_code,'') ILIKE :ql
            OR COALESCE(treatment_code,'')      ILIKE :ql
            OR COALESCE(treat_text,'')          ILIKE :ql
            OR COALESCE(cross_code,'')         ILIKE :ql
            OR COALESCE(tank_pair_code,'')     ILIKE :ql
            OR COALESCE(parent_cross_pretty,'') ILIKE :ql
        )
        AND (:from_d IS NULL OR clutch_date >= :from_d)
        AND (:to_d   IS NULL OR clutch_date <= :to_d)
        ORDER BY clutch_date DESC NULLS LAST,
                 clutch_code,
                 level,
                 treated_clutch_code NULLS FIRST
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
    """
    Expected genotypes for a clutch from clutch_genotypes_v11 + genotypes_v11,
    with 3 display styles:

      - genotype_tg_style
      - genotype_fluortag_style
      - genotype_fluororganelle_style
    """
    sql = text(
        """
        WITH base AS (
          SELECT
            cg.id::uuid          AS clutch_genotype_id,
            cg.clutch_id::uuid   AS clutch_id,
            cg.is_enabled        AS is_enabled,
            cg.expected_fraction AS expected_fraction,
            cg.expected_percent_label AS expected_percent_label,
            cg.notes             AS notes,
            cg.created_at,
            cg.created_by,
            g.id::uuid           AS genotype_id,
            g.genotype_code,
            g.genotype_basecodes,
            g.genotype_pretty
          FROM public.clutch_genotypes_v11 cg
          JOIN public.genotypes_v11 g
            ON g.id = cg.genotype_v11_id
          WHERE cg.clutch_id = :cid
        ),
        constructs AS (
          SELECT
            b.genotype_id,
            c.construct_code,
            vco.fusion_pretty,
            vco.organelle_fluors
          FROM base b
          LEFT JOIN public.join_genotype_constructs_v11 j
            ON j.genotype_id = b.genotype_id
          LEFT JOIN public.constructs c
            ON c.id = j.construct_id
          LEFT JOIN public.v_constructs_overview vco
            ON vco.construct_code = c.construct_code
        ),
        agg AS (
          SELECT
            genotype_id,
            string_agg(DISTINCT fusion_pretty, '; ' ORDER BY fusion_pretty) AS fluor_tag_style,
            string_agg(DISTINCT organelle_fluors, '; ' ORDER BY organelle_fluors) AS fluor_organelle_style
          FROM constructs
          GROUP BY genotype_id
        )
        SELECT
          b.clutch_genotype_id::text         AS clutch_genotype_id,
          b.genotype_code,
          b.genotype_basecodes               AS genotype_basecode_code,
          b.genotype_pretty                  AS genotype_transgene_allele_code,
          b.is_enabled,
          b.expected_fraction,
          b.expected_percent_label,
          b.notes,
          b.created_at,
          b.created_by,
          COALESCE(a.fluor_tag_style, '')        AS genotype_fluortag_style,
          COALESCE(a.fluor_organelle_style, '')  AS genotype_fluororganelle_style
        FROM base b
        LEFT JOIN agg a
          ON a.genotype_id = b.genotype_id
        ORDER BY b.genotype_code;
        """
    )
    with eng().begin() as cx:
        df = pd.read_sql(sql, cx, params={"cid": clutch_id})

    # Compute tg-style from basecodes in Python
    def _tg_style(basecodes: Any) -> str:
        txt = str(basecodes or "").strip()
        if not txt:
            return ""
        parts: List[str] = []
        for tok in txt.split(","):
            t = tok.strip()
            if not t:
                continue
            if ":" in t:
                base, num = t.split(":", 1)
                base = base.strip()
                num = num.strip()
                if base and num:
                    parts.append(f"Tg({base}){num}")
                elif base:
                    parts.append(f"Tg({base})")
            else:
                parts.append(f"Tg({t})")
        return " + ".join(parts)

    df["genotype_tg_style"] = df["genotype_basecode_code"].map(_tg_style)
    return df.fillna("")


@st.cache_data(show_spinner=False)
def load_selection_events_for_target(
    clutch_id: str,
    treated_clutch_id: Optional[str],
) -> pd.DataFrame:
    """
    Existing selection events for a (clutch, treated_clutch) target.
    """
    sql = text(
        """
        SELECT
          selection_event_id::text       AS selection_event_id,
          selection_kind,
          selection_label,
          selection_created_at,
          created_by,
          clutch_id::text                AS clutch_id,
          clutch_code,
          clutch_date,
          treated_clutch_id::text        AS treated_clutch_id,
          treated_clutch_code,
          treatment_code,
          treat_text,
          genotype_code,
          genotype_basecodes,
          genotype_pretty,
          is_primary,
          notes
        FROM public.v11_clutch_selection_star
        WHERE clutch_id::text = :cid
          AND (
                (:tcid IS NULL AND treated_clutch_id IS NULL)
             OR (:tcid IS NOT NULL AND treated_clutch_id::text = :tcid)
          )
        ORDER BY selection_created_at DESC NULLS LAST,
                 selection_event_id,
                 genotype_code;
        """
    )
    with eng().begin() as cx:
        df = pd.read_sql(
            sql,
            cx,
            params={"cid": clutch_id, "tcid": treated_clutch_id},
        )
    return df.fillna("")


# ───────── Step 1 — pick a target (clutch or treated clutch) ─────────

with st.form("clutch_filters_for_selection", clear_on_submit=False):
    c1, c2, c3, c4 = st.columns([3, 1.5, 1.5, 1])
    with c1:
        q_raw = st.text_input(
            "Search (clutch / treated clutch / treatment / cross / parent FSH)",
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

rows = load_target_clutches_for_selection(q, from_d, to_d, lim)

if rows.empty:
    st.info("No clutches or treated clutches match the current filters.")
    st.stop()

st.subheader("Step 1 — Select a target (clutch or treated clutch)", anchor=False)

view = rows.copy()
view.insert(0, "✓ Select", False)

visible_cols = [
    "✓ Select",
    "level",
    "clutch_code",
    "clutch_date",
    "treated_clutch_code",
    "treatment_code",
    "treat_text",
    "cross_code",
    "cross_date",
    "tank_pair_code",
    "parent_cross_pretty",
    "n_selection_events",
]
visible_cols = [c for c in visible_cols if c in view.columns]

grid = st.data_editor(
    view[visible_cols],
    key="clutch_selection_target_grid_v11",
    hide_index=True,
    width="stretch",
    num_rows="fixed",
    column_config={
        "✓ Select": st.column_config.CheckboxColumn("✓", default=False),
        "level": st.column_config.TextColumn("Level", disabled=True),
        "clutch_code": st.column_config.TextColumn("Clutch", disabled=True),
        "clutch_date": st.column_config.DateColumn("Clutch date", disabled=True),
        "treated_clutch_code": st.column_config.TextColumn(
            "Treated clutch", disabled=True
        ),
        "treatment_code": st.column_config.TextColumn("Treatment code", disabled=True),
        "treat_text": st.column_config.TextColumn(
            "Treatment text", disabled=True, width="large"
        ),
        "cross_code": st.column_config.TextColumn("Cross", disabled=True),
        "cross_date": st.column_config.DateColumn("Cross date", disabled=True),
        "tank_pair_code": st.column_config.TextColumn("Tank pair", disabled=True),
        "parent_cross_pretty": st.column_config.TextColumn(
            "Parents (FSH × FSH)", disabled=True, width="large"
        ),
        "n_selection_events": st.column_config.NumberColumn(
            "# selection events", disabled=True
        ),
    },
)

sel_mask = (
    grid.get("✓ Select", pd.Series(False, index=grid.index))
    .fillna(False)
    .astype(bool)
)
selected_idx = grid.index[sel_mask]

if selected_idx.empty:
    st.info("Select one target row above to work with selections.")
    st.stop()

base_row = rows.loc[selected_idx].iloc[0]
target_level = str(base_row["level"])
clutch_id = str(base_row["clutch_id"])
clutch_code = str(base_row["clutch_code"])
clutch_date = base_row.get("clutch_date")
treated_clutch_id = (
    str(base_row["treated_clutch_id"]) if base_row.get("treated_clutch_id") else None
)
treated_clutch_code = base_row.get("treated_clutch_code") or ""
treatment_code = base_row.get("treatment_code") or ""

scope_str = "treated_clutch" if treated_clutch_id else "clutch"

if treated_clutch_id:
    st.success(
        f"Selected target: treated clutch {treated_clutch_code} for clutch {clutch_code} "
        f"(scope={scope_str}, clutch_date={clutch_date}, treatment={treatment_code})"
    )
else:
    st.success(
        f"Selected target: clutch {clutch_code} (scope={scope_str}, clutch_date={clutch_date})"
    )

# ───────── Existing selection events for this target ─────────
st.markdown("---")
st.subheader("Existing selection events for this target", anchor=False)

sel_df = load_selection_events_for_target(clutch_id, treated_clutch_id)

if sel_df.empty:
    st.info("No selection events recorded yet for this target.")
else:
    st.dataframe(
        sel_df[
            [
                "selection_created_at",
                "selection_kind",
                "selection_label",
                "treated_clutch_code",
                "treatment_code",
                "treat_text",
                "genotype_code",
                "genotype_basecodes",
                "genotype_pretty",
                "is_primary",
                "created_by",
                "notes",
            ]
        ],
        hide_index=True,
        width="stretch",
    )

# ───────── Step 2 — Expected genotypes (for the clutch) ─────────
st.markdown("---")
st.subheader("Step 2 — Expected genotypes (pick which to link)", anchor=False)

eg = load_expected_genotypes(clutch_id)

if eg.empty:
    st.info(
        "No expected genotypes recorded for this clutch yet. "
        "You can still save a selection event (it will just have no genotype links)."
    )
    eg_selected = pd.DataFrame()
else:
    eg_view = eg.copy()
    eg_view.insert(0, "✓ Use", True)
    eg_view.insert(1, "Primary", False)

    eg_grid = st.data_editor(
        eg_view[
            [
                "✓ Use",
                "Primary",
                "genotype_code",
                "genotype_tg_style",
                "genotype_fluortag_style",
                "genotype_fluororganelle_style",
                "genotype_basecode_code",
                "genotype_transgene_allele_code",
            ]
        ],
        key="selection_genotype_picker_v11",
        hide_index=True,
        width="stretch",
        num_rows="fixed",
        column_config={
            "✓ Use": st.column_config.CheckboxColumn("Use", default=True),
            "Primary": st.column_config.CheckboxColumn("Primary", default=False),
            "genotype_code": st.column_config.TextColumn(
                "Genotype code", disabled=True
            ),
            "genotype_tg_style": st.column_config.TextColumn(
                "Genotype (tg)", disabled=True, width="large"
            ),
            "genotype_fluortag_style": st.column_config.TextColumn(
                "Genotype (fluor-tag)", disabled=True, width="large"
            ),
            "genotype_fluororganelle_style": st.column_config.TextColumn(
                "Genotype (fluor-organelle)", disabled=True, width="large"
            ),
            "genotype_basecode_code": st.column_config.TextColumn(
                "Basecodes", disabled=True, width="large"
            ),
            "genotype_transgene_allele_code": st.column_config.TextColumn(
                "Genotype (raw)", disabled=True, width="large"
            ),
        },
    )

    use_mask = (
        eg_grid["✓ Use"] == True
        if "✓ Use" in eg_grid.columns
        else pd.Series(False, index=eg_grid.index)
    )
    eg_selected = eg_grid[use_mask].copy()

    if eg_selected.empty:
        st.caption(
            "No genotypes selected — this selection event will be recorded with no genotype narrowing."
        )
    else:
        prim_mask = (
            eg_selected["Primary"] == True
            if "Primary" in eg_selected.columns
            else pd.Series(False, index=eg_selected.index)
        )
        if prim_mask.sum() > 1:
            st.warning(
                "Multiple genotypes marked as Primary; the first will be stored as primary."
            )

    use_mask = (
        eg_grid["✓ Use"] == True
        if "✓ Use" in eg_grid.columns
        else pd.Series(False, index=eg_grid.index)
    )
    eg_selected = eg_grid[use_mask].copy()

    if eg_selected.empty:
        st.caption(
            "No genotypes selected — this selection event will be recorded with no genotype narrowing."
        )
    else:
        prim_mask = (
            eg_selected["Primary"] == True
            if "Primary" in eg_selected.columns
            else pd.Series(False, index=eg_selected.index)
        )
        if prim_mask.sum() > 1:
            st.warning(
                "Multiple genotypes marked as Primary; the first will be stored as primary."
            )

# ───────── Step 3 — Selection label, notes & save ─────────
st.markdown("---")
st.subheader("Step 3 — Selection label, notes & save", anchor=False)

st.markdown(
    """
**How to use these fields:**

- **Selection label**: a short name for this selection event, e.g.  
  • `bright green and red`  
  • `kept for imaging`  
  • `nursery intake`  
  • `rare survivors`

- **Selection notes**: optional longer description of *why* you selected this group.  
  Include phenotype, imaging context, or anything that will help you remember later.
"""
)

with st.form("selection_metadata_form", clear_on_submit=False):
    label = st.text_input(
        "Selection label (required)",
        "",
    )
    notes = st.text_area(
        "Selection notes (optional)",
        "",
        height=80,
    )

    submit = st.form_submit_button("💾 Save selection event", use_container_width=True)

if submit:
    if not label.strip():
        st.error("Selection label is required.")
    else:
        # Prepare genotype links (optional narrowing)
        genotype_rows: List[Dict[str, Any]] = []
        if not eg_selected.empty and "clutch_genotype_id" in eg_selected.columns:
            eg_by_code = eg.set_index("genotype_code") if not eg.empty else None
            for _, r in eg_selected.iterrows():
                code = str(r.get("genotype_code") or "")
                if not code:
                    continue
                row_src = (
                    eg_by_code.loc[code]
                    if eg_by_code is not None and code in eg_by_code.index
                    else None
                )
                if row_src is None:
                    continue
                genotype_rows.append(
                    {
                        "clutch_genotype_id": str(row_src["clutch_genotype_id"]),
                        "is_primary": bool(r.get("Primary", False)),
                    }
                )
            # Ensure at most one primary genotype
            prim_indices = [i for i, gr in enumerate(genotype_rows) if gr["is_primary"]]
            if len(prim_indices) > 1:
                keep = prim_indices[0]
                for i in prim_indices[1:]:
                    genotype_rows[i]["is_primary"] = False

        try:
            with eng().begin() as cx:
                treated_clutch_id_val = treated_clutch_id

                # Insert into clutch_selection_events_v11 using only real columns
                sel_row = cx.execute(
                    text(
                        """
                        INSERT INTO public.clutch_selection_events_v11 (
                          id,
                          clutch_id,
                          treated_clutch_id,
                          selection_kind,
                          selection_label,
                          notes,
                          created_at,
                          created_by
                        )
                        VALUES (
                          gen_random_uuid(),
                          :clutch_id,
                          :treated_clutch_id,
                          'manual',
                          :label,
                          :notes,
                          now(),
                          :created_by
                        )
                        RETURNING id::text AS selection_event_id;
                        """
                    ),
                    {
                        "clutch_id": clutch_id,
                        "treated_clutch_id": treated_clutch_id_val,
                        "label": label.strip(),
                        "notes": notes.strip() or None,
                        "created_by": _who(),
                    },
                ).fetchone()

                selection_event_id = sel_row._mapping["selection_event_id"]

                # Insert genotype links (if any) into clutch_selection_genotypes_v11
                for gr in genotype_rows:
                    cx.execute(
                        text(
                            """
                            INSERT INTO public.clutch_selection_genotypes_v11 (
                              id,
                              selection_event_id,
                              clutch_genotype_id,
                              is_primary,
                              created_at,
                              created_by
                            )
                            VALUES (
                              gen_random_uuid(),
                              :sid::uuid,
                              :gid::uuid,
                              :primary,
                              now(),
                              :by
                            )
                            ON CONFLICT (selection_event_id, clutch_genotype_id) DO NOTHING;
                            """
                        ),
                        {
                            "sid": selection_event_id,
                            "gid": gr["clutch_genotype_id"],
                            "primary": gr["is_primary"],
                            "by": _who(),
                        },
                    )

            target_desc = (
                f"treated clutch {treated_clutch_code}"
                if treated_clutch_id
                else f"clutch {clutch_code}"
            )
            # bust caches so the next interaction shows fresh data
            st.cache_data.clear()

            st.success(
                f"Saved selection '{label.strip()}' for {target_desc}, "
                f"{len(genotype_rows)} genotype link(s)."
            )
        except Exception as e:
            st.error(f"Save selection failed: {type(e).__name__}: {e}")