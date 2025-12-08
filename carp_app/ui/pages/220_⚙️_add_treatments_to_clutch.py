from __future__ import annotations

import sys
import os
import pathlib
from datetime import datetime
from typing import Optional

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
from carp_app.ui.lib.page_engine import engine as _create_engine

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


# ───────── engine ─────────
def eng() -> Engine:
    return _create_engine()


def _norm(s: str | None) -> Optional[str]:
    s = (s or "").strip()
    return s or None


# ───────── loaders ─────────
@st.cache_data(show_spinner=False)
def load_clutches(
    q: Optional[str],
    from_date: Optional[str],
    to_date: Optional[str],
    limit: int,
) -> pd.DataFrame:
    """
    Clutch list using v11_clutch_flat_overview (level = 'clutch'),
    limited to modern clutches (excludes source_system = 'legacy_imaging').

    Includes cross / tank / parents and standard label fields.
    """
    sql = text(
        """
        SELECT
          f.clutch_id::text AS clutch_id,
          f.clutch_code,
          f.clutch_date,
          f.cross_code,
          f.cross_date,
          f.tank_pair_code,
          f.parent_cross_pretty,
          f.transgene_label,
          f.fluor_tag_label,
          f.organelle_fluor_label
        FROM public.v11_clutch_flat_overview AS f
        JOIN public.clutches AS c
          ON c.id = f.clutch_id
        WHERE f.level = 'clutch'
          AND (c.source_system IS NULL OR c.source_system <> 'legacy_imaging')
          AND (
               :q IS NULL
            OR f.clutch_code             ILIKE :ql
            OR COALESCE(f.cross_code,'') ILIKE :ql
            OR COALESCE(f.tank_pair_code,'') ILIKE :ql
            OR COALESCE(f.parent_cross_pretty,'') ILIKE :ql
          )
          AND (:from_d IS NULL OR f.clutch_date >= :from_d)
          AND (:to_d   IS NULL OR f.clutch_date <= :to_d)
        ORDER BY f.clutch_date DESC NULLS LAST, f.clutch_code
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


def load_treatments() -> pd.DataFrame:
    """
    Treatment overview using label styles from v11_treatment_label_star
    and counts from treatment_mixes / constructs / dyes.

    Includes:
      • n_constructs / n_dyes (from mix tables)
      • genotype_basecode_code  → tg(basecode) style
      • fluor_tag_style         → fluor::tag(tag_pos)
      • fluor_organelle_style   → organelle–fluor
    """
    sql = text(
        """
        WITH mix_counts AS (
          SELECT
            tm.treatment_id::text AS treatment_id,
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
          tl.treatment_id,
          tl.treat_code             AS treatment_code,
          tl.kind_code,
          tl.treat_text,
          COALESCE(mc.n_constructs, 0)    AS n_constructs,
          COALESCE(mc.n_dyes, 0)          AS n_dyes,
          tl.genotype_basecode_code,
          tl.fluor_tag_style,
          tl.fluor_organelle_style
        FROM public.v11_treatment_label_star tl
        LEFT JOIN mix_counts mc
          ON mc.treatment_id = tl.treatment_id
        ORDER BY tl.treat_code;
        """
    )
    with eng().begin() as cx:
        df = pd.read_sql(sql, cx)
    return df.fillna("")


def load_treated_clutches(clutch_id: str) -> pd.DataFrame:
    """
    Treated clutch subgroups for a given clutch, with standard display fields.

    Uses v11_clutch_flat_overview (level = 'treated_clutch') for labels,
    and treated_clutches_v11 for notes.
    """
    sql = text(
        """
        WITH flat AS (
          SELECT
            treated_clutch_id,
            treated_clutch_code,
            treatment_code,
            transgene_label,
            fluor_tag_label,
            organelle_fluor_label
          FROM public.v11_clutch_flat_overview
          WHERE level = 'treated_clutch'
            AND clutch_id::text = :cid
        )
        SELECT
          tc.id::text              AS id,
          f.treated_clutch_code,
          f.treatment_code,
          f.transgene_label,
          f.fluor_tag_label,
          f.organelle_fluor_label,
          tc.notes
        FROM public.treated_clutches_v11 tc
        JOIN flat f
          ON f.treated_clutch_id = tc.id
        ORDER BY f.treated_clutch_code;
        """
    )
    with eng().begin() as cx:
        df = pd.read_sql(sql, cx, params={"cid": clutch_id})
    return df.fillna("")


# ───────── Step 1 — select a clutch ─────────
with st.form("clutch_filters", clear_on_submit=False):
    c1, c2, c3, c4 = st.columns([3, 1.5, 1.5, 1])
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

clutches_df = load_clutches(q, from_d, to_d, lim)

if clutches_df.empty:
    st.info("No clutches match the current filters.")
    st.stop()

st.subheader("Step 1 — Select a clutch", anchor=False)

clutch_rows = clutches_df.copy()
clutch_rows.insert(0, "✓ Select", False)

visible_cols = [
    "✓ Select",
    "clutch_code",
    "clutch_date",
    "cross_code",
    "cross_date",
    "tank_pair_code",
    "parent_cross_pretty",
    "transgene_label",
    "fluor_tag_label",
    "organelle_fluor_label",
]
visible_cols = [c for c in visible_cols if c in clutch_rows.columns]

clutch_column_config: dict[str, st.column_config.BaseColumn] = {
    "✓ Select": st.column_config.CheckboxColumn("✓", default=False),
    "clutch_code": st.column_config.TextColumn("Clutch", disabled=True),
    "clutch_date": st.column_config.TextColumn("Clutch date", disabled=True),
    "cross_code": st.column_config.TextColumn("Cross", disabled=True),
    "cross_date": st.column_config.TextColumn("Cross date", disabled=True),
    "tank_pair_code": st.column_config.TextColumn("Tank pair", disabled=True),
    "parent_cross_pretty": st.column_config.TextColumn("Parents", disabled=True),
}
if "transgene_label" in clutch_rows.columns:
    clutch_column_config["transgene_label"] = st.column_config.TextColumn(
        "Transgene tg(basecode)allele", disabled=True
    )
if "fluor_tag_label" in clutch_rows.columns:
    clutch_column_config["fluor_tag_label"] = st.column_config.TextColumn(
        "Fluor–tag fluor::tag(tag_pos)", disabled=True
    )
if "organelle_fluor_label" in clutch_rows.columns:
    clutch_column_config["organelle_fluor_label"] = st.column_config.TextColumn(
        "Organelles organelle–fluor", disabled=True
    )

clutch_grid = st.data_editor(
    clutch_rows[visible_cols],
    key="clutch_picker_grid_v11",
    hide_index=True,
    width="stretch",
    num_rows="fixed",
    column_config=clutch_column_config,
)

sel_mask = clutch_grid["✓ Select"] == True if "✓ Select" in clutch_grid.columns else pd.Series(False, index=clutch_grid.index)
selected_idx = clutch_grid.index[sel_mask]

if selected_idx.empty:
    st.info("Select one clutch above to define its treated groups.")
    st.stop()

base_row = clutches_df.loc[selected_idx].iloc[0]
clutch_id = base_row["clutch_id"]
clutch_code = base_row["clutch_code"]
cross_code = base_row.get("cross_code", "")
parent_cross_pretty = base_row.get("parent_cross_pretty", "")

st.success(
    f"Selected clutch: {clutch_code} (cross {cross_code}, parents {parent_cross_pretty})"
)

# naming hint: TREAT-CL-<uuid8>-NN
cl_uuid8 = str(clutch_id).replace("-", "")[:8] if clutch_id else ""
prefix = f"TREAT-CL-{cl_uuid8}-"
st.caption(
    f"Treat group names often follow the pattern `{prefix}NN` "
    f"(with `{prefix}00` reserved for untreated)."
)

# ───────── load current treated groups ─────────
treated_groups = load_treated_clutches(clutch_id)

# ───────── Step 2 — select treatment and create treated groups ─────────
st.subheader("Step 2 — Select treatment and create treated groups", anchor=False)

treatments_df = load_treatments()
if treatments_df.empty:
    st.info("No treatments found in public.treatments.")
else:
    tcol1, tcol2 = st.columns([3, 1])
    with tcol1:
        t_filter_raw = st.text_input(
            "Filter treatments (code / kind / text / fluor / organelle)",
            "",
            key="treatment_filter_v11",
        )
    with tcol2:
        st.caption(f"Existing treated groups: **{len(treated_groups)}**")

    t_filter = _norm(t_filter_raw)
    t_view = treatments_df.copy()

    if t_filter:
        mask = (
            t_view["treatment_code"].str.contains(t_filter, case=False, na=False)
            | t_view["kind_code"].str.contains(t_filter, case=False, na=False)
            | t_view["treat_text"].str.contains(t_filter, case=False, na=False)
            | t_view["genotype_basecode_code"].str.contains(t_filter, case=False, na=False)
            | t_view["fluor_tag_style"].str.contains(t_filter, case=False, na=False)
            | t_view["fluor_organelle_style"].str.contains(t_filter, case=False, na=False)
        )
        t_view = t_view[mask].copy()

    if t_view.empty:
        st.info("No treatments match the current filter.")
    else:
        t_view = t_view.copy()
        t_view.insert(0, "✓ Select", False)

        t_grid = st.data_editor(
            t_view[
                [
                    "✓ Select",
                    "treatment_code",
                    "kind_code",
                    "treat_text",
                    "n_constructs",
                    "n_dyes",
                    "genotype_basecode_code",
                    "fluor_tag_style",
                    "fluor_organelle_style",
                ]
            ],
            key="treatment_picker_grid_v11",
            hide_index=True,
            width="stretch",
            num_rows="fixed",
            column_config={
                "✓ Select": st.column_config.CheckboxColumn("✓", default=False),
                "treatment_code": st.column_config.TextColumn("Treat code", disabled=True),
                "kind_code": st.column_config.TextColumn("Kind", disabled=True),
                "treat_text": st.column_config.TextColumn("Description", disabled=True),
                "n_constructs": st.column_config.NumberColumn("n_constructs", disabled=True),
                "n_dyes": st.column_config.NumberColumn("n_dyes", disabled=True),
                "genotype_basecode_code": st.column_config.TextColumn(
                    "Transgene tg(basecode)allele", disabled=True
                ),
                "fluor_tag_style": st.column_config.TextColumn(
                    "Fluor–tag fluor::tag(tag_pos)", disabled=True
                ),
                "fluor_organelle_style": st.column_config.TextColumn(
                    "Organelles organelle–fluor", disabled=True
                ),
            },
        )

        t_sel_mask = t_grid["✓ Select"] == True if "✓ Select" in t_grid.columns else pd.Series(False, index=t_grid.index)
        t_sel = t_grid[t_sel_mask]

        selected_treat_code: Optional[str] = None
        if not t_sel.empty:
            selected_treat_code = t_sel.iloc[0]["treatment_code"]

        if st.button("➕ Add treated group for selected treatment", type="secondary"):
            if not selected_treat_code:
                st.error("Select a treatment above first.")
            else:
                try:
                    with eng().begin() as cx:
                        # resolve treatment_id
                        tid = cx.execute(
                            text(
                                """
                                SELECT id
                                FROM public.treatments
                                WHERE treat_code = :code
                                LIMIT 1;
                                """
                            ),
                            {"code": selected_treat_code},
                        ).scalar()

                        if not tid:
                            st.error(f"Unknown treatment_code: {selected_treat_code}")
                        else:
                            # compute next suffix NN (start at 01, not 00)
                            existing_codes = [
                                str(c).strip()
                                for c in load_treated_clutches(clutch_id)["treated_clutch_code"].tolist()
                            ]
                            used_suffixes = set()
                            for code in existing_codes:
                                if code.startswith(prefix):
                                    suff = code[len(prefix):]
                                    if len(suff) == 2 and suff.isdigit():
                                        used_suffixes.add(int(suff))
                            next_n = 1
                            while next_n in used_suffixes and next_n < 100:
                                next_n += 1
                            new_code = f"{prefix}{next_n:02d}"

                            # insert treated_clutches_v11 row
                            cx.execute(
                                text(
                                    """
                                    INSERT INTO public.treated_clutches_v11 (
                                      clutch_id,
                                      treated_clutch_code,
                                      treatment_id,
                                      notes,
                                      created_by
                                    )
                                    VALUES (
                                      :clutch_id,
                                      :treated_clutch_code,
                                      :treatment_id,
                                      NULL,
                                      :created_by
                                    );
                                    """
                                ),
                                {
                                    "clutch_id": clutch_id,
                                    "treated_clutch_code": new_code,
                                    "treatment_id": tid,
                                    "created_by": getattr(user, "email", None)
                                                  or os.getenv("USER")
                                                  or os.getenv("USERNAME")
                                                  or "system",
                                },
                            )

                            # ensure join_clutch_treatments link exists
                            cx.execute(
                                text(
                                    """
                                    INSERT INTO public.join_clutch_treatments (
                                      id,
                                      clutch_id,
                                      treatment_id,
                                      applied_at,
                                      notes
                                    )
                                    VALUES (
                                      gen_random_uuid(),
                                      :clutch_id,
                                      :treatment_id,
                                      now(),
                                      NULL
                                    )
                                    ON CONFLICT (clutch_id, treatment_id) DO NOTHING;
                                    """
                                ),
                                {"clutch_id": clutch_id, "treatment_id": tid},
                            )

                    st.success(
                        f"Added treated group {new_code} with treatment {selected_treat_code}."
                    )
                    st.rerun()
                except Exception as e:
                    st.error(f"Add treated group failed: {type(e).__name__}: {e}")

# reload treated groups after potential insert
treated_groups = load_treated_clutches(clutch_id)

# ───────── Step 2b — existing treated groups (edit code / notes) ─────────
st.subheader("Existing treated groups for this clutch", anchor=False)

if treated_groups.empty:
    st.info("No treated groups defined yet for this clutch.")
else:
    groups_view = treated_groups[
        [
            "treated_clutch_code",
            "treatment_code",
            "transgene_label",
            "fluor_tag_label",
            "organelle_fluor_label",
            "notes",
        ]
    ].copy()

    groups_grid = st.data_editor(
        groups_view,
        key="treated_clutches_editor_v11",
        hide_index=True,
        width="stretch",
        num_rows="fixed",
        column_config={
            "treated_clutch_code": st.column_config.TextColumn("Treated clutch code"),
            "treatment_code": st.column_config.TextColumn("Treatment code", disabled=True),
            "transgene_label": st.column_config.TextColumn("Transgene tg(basecode)allele", disabled=True),
            "fluor_tag_label": st.column_config.TextColumn("Fluor–tag fluor::tag(tag_pos)", disabled=True),
            "organelle_fluor_label": st.column_config.TextColumn("Organelles organelle–fluor", disabled=True),
            "notes": st.column_config.TextColumn("Notes"),
        },
    )

    st.caption(
        "You can rename treated_clutch_code and set notes for each group. "
        "Treatment code is fixed for an existing group; to change it, create a new group."
    )

    # ───────── Step 3 — save edits to existing groups ─────────
    st.subheader("Step 3 — Save treated clutch group edits", anchor=False)

    if st.button("💾 Save treated group edits", type="primary"):
        try:
            merged = treated_groups[["id"]].join(groups_grid)

            updated = 0
            with eng().begin() as cx:
                for _, row in merged.iterrows():
                    res = cx.execute(
                        text(
                            """
                            UPDATE public.treated_clutches_v11
                            SET
                            treated_clutch_code = :treated_clutch_code,
                            notes               = :notes
                            WHERE id = :id;
                            """
                        ),
                        {
                            "id": row["id"],
                            "treated_clutch_code": (row.get("treated_clutch_code") or "").strip(),
                            "notes": (row.get("notes") or "").strip() or None,
                        },
                    )
                    updated += res.rowcount

            if updated > 0:
                st.success(f"Updated {updated} treated clutch group(s).")
            else:
                st.info("No changes detected; treated clutch groups are unchanged.")
        except Exception as e:
            st.error(f"Save edits failed: {type(e).__name__}: {e}")

# ───────── Step 4 — export ─────────
st.subheader("Step 4 — Download treated clutch groups (CSV)", anchor=False)

csv_bytes = treated_groups.to_csv(index=False).encode("utf-8")
st.download_button(
    "⬇︎ Download treated clutch groups (CSV)",
    data=csv_bytes,
    file_name=f"{clutch_code}_treated_clutches_v11.csv",
    type="secondary",
    mime="text/csv",
)