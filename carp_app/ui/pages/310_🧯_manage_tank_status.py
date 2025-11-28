# carp_app/ui/pages/310_🧯_manage_tank_status.py
# Simple v11 Manage Tank Status: fish summary view → tanks for selected fish

from __future__ import annotations
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[3]))

import os
from typing import List, Any

import pandas as pd
import streamlit as st
from sqlalchemy import text, bindparam
from sqlalchemy.engine import Engine
from sqlalchemy.dialects.postgresql import ARRAY

from carp_app.lib.db import get_engine
from carp_app.ui.auth_gate import require_auth
from carp_app.ui.email_otp_gate import require_email_otp

# ── Auth ─────────────────────────────────────────────────────────────────────
sb, session, user = require_auth()
require_email_otp()

# ── Page ─────────────────────────────────────────────────────────────────────
st.set_page_config(page_title="🧯 Manage Tank Status (v11)", page_icon="🧯", layout="wide")
st.title("🧯 Manage Tank Status")

ENG: Engine = get_engine()

# ── Helpers ──────────────────────────────────────────────────────────────────
def _safe(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, (pd.Timestamp,)):
        return v.strftime("%Y-%m-%d")
    return str(v)

def _distinct_statuses() -> list[str]:
    # simple, hard-coded status set
    return ["new_tank", "active", "to_kill", "retired", "planned"]

# ── Data loaders ─────────────────────────────────────────────────────────────
def _load_fish_summary(q: str | None, limit: int) -> pd.DataFrame:
    """
    Top fish table: one row per fish_code, from v11_fish_tank_summary.
    """
    qnorm = (q or "").strip()
    sql = text("""
      SELECT
        fish_code,
        birthday,
        genotype_basecode_code,
        genotype_transgene_allele_code,
        treatment_code,
        treatments_and_transgenes,
        all_fluor_tag_rollup,
        all_organelle_fluor_rollup,
        n_tanks
      FROM public.v11_fish_tank_summary
      WHERE (:q IS NULL)
         OR fish_code                 ILIKE :ql
         OR genotype_basecode_code    ILIKE :ql
         OR genotype_transgene_allele_code ILIKE :ql
         OR treatment_code            ILIKE :ql
         OR treatments_and_transgenes ILIKE :ql
      ORDER BY birthday DESC NULLS LAST, fish_code
      LIMIT :lim
    """)
    params = {
        "q":  (qnorm if qnorm else None),
        "ql": f"%{qnorm}%",
        "lim": int(limit),
    }
    with ENG.begin() as cx:
        df = pd.read_sql(sql, cx, params=params)
    for c in df.select_dtypes(include="object").columns:
        df[c] = df[c].astype("string").fillna("")
    return df

def _load_tanks_for_fish(fish_code: str) -> pd.DataFrame:
    """
    Tanks for a single fish_code, from public.v_tanks_overview.
    Uses tank_id (text) as the ID we act on.
    """
    sql = text("""
      SELECT
        tank_id::text                     AS id,
        tank_code::text                   AS tank_code,
        fish_code::text                   AS fish_code,
        COALESCE(status::text,'')        AS status,
        created_at
      FROM public.v_tanks_overview
      WHERE fish_code = :fish
      ORDER BY created_at DESC NULLS LAST, tank_code
      LIMIT 1000
    """)
    with ENG.begin() as cx:
        df = pd.read_sql(sql, cx, params={"fish": fish_code})
    for c in df.select_dtypes(include="object").columns:
        df[c] = df[c].astype("string").fillna("")
    return df

def _bulk_update_status(tank_ids: List[str], new_status: str) -> int:
    """
    Simple status update on public.tanks, using id that matches v_tanks_overview.tank_id.
    """
    if not tank_ids:
        return 0
    sql = text("""
      UPDATE public.tanks
         SET status = :st
       WHERE id = ANY(CAST(:ids AS uuid[]))
    """)
    with ENG.begin() as cx:
        cx.execute(sql, {"st": new_status, "ids": tank_ids})
    return len(tank_ids)

def _create_new_tanks_for_fish(fish_code: str, n: int) -> pd.DataFrame:
    """
    Create N new tanks for a fish_code.

    Semantics: fish_instance_id represents a group of animals, and that group
    can live in multiple tanks. We attach the same fish_instance_id to the new tanks.
    """
    if n <= 0:
        return pd.DataFrame()

    # 1. Resolve fish_instance_id for this fish_code
    sql_fi = text("""
      SELECT fish_instance_id
      FROM public.v11_fish_instance_star
      WHERE fish_code = :fish
      ORDER BY fish_created_at DESC NULLS LAST
      LIMIT 1
    """)
    with ENG.begin() as cx:
        fi_df = pd.read_sql(sql_fi, cx, params={"fish": fish_code})
    if fi_df.empty:
        return pd.DataFrame()
    fish_instance_id = fi_df["fish_instance_id"].iloc[0]

    # 2. Compute base index from v_tanks_overview for this fish_code
    sql_idx = text("""
      SELECT COALESCE(
               MAX((regexp_match(tank_code, '#([0-9]+)$'))[1]::int),
               0
             ) AS base_idx
      FROM public.v_tanks_overview
      WHERE fish_code = :fish
    """)
    with ENG.begin() as cx:
        base_idx = pd.read_sql(sql_idx, cx, params={"fish": fish_code})["base_idx"].iloc[0]

    # 3. Insert new tanks bound to this fish_instance_id
    sql_ins = text("""
      INSERT INTO public.tanks (id, tank_code, fish_instance_id, status, created_at)
      SELECT
        gen_random_uuid(),
        format('TANK(%s)#%s', :fish, :base + g.i),
        :fi,
        'new_tank',
        now()
      FROM generate_series(1, :n) AS g(i)
      RETURNING id::text AS id, tank_code::text, fish_instance_id::text, status, created_at
    """)
    with ENG.begin() as cx:
        df = pd.read_sql(sql_ins, cx, params={
            "fish": fish_code,
            "base": int(base_idx),
            "n": int(n),
            "fi": fish_instance_id,
        })
    return df

# ── Filters ──────────────────────────────────────────────────────────────────
with st.form("filters"):
    c1, c2 = st.columns([3,1])
    with c1:
        fish_query = st.text_input("Search fish (code / genotype / treatment)", value="")
    with c2:
        limit = int(st.number_input("Max fish", min_value=10, max_value=2000, value=500, step=50))
    _ = st.form_submit_button("Apply", use_container_width=True)

# ── Step 1 — Fish summary ────────────────────────────────────────────────────
fish_df = _load_fish_summary(fish_query, limit)
st.subheader("1) Fish with tanks (summary)")

if fish_df.empty:
    st.info("No fish have tanks (or none match your filter)."); st.stop()

fish_sel_col = "✓ Select fish"
fish_grid = fish_df.copy()
if fish_sel_col not in fish_grid.columns:
    fish_grid.insert(0, fish_sel_col, False)

fish_view = fish_grid[[
    fish_sel_col,
    "fish_code",
    "n_tanks",
    "birthday",
    "genotype_basecode_code",
    "genotype_transgene_allele_code",
    "treatment_code",
    "treatments_and_transgenes",
    "all_fluor_tag_rollup",
    "all_organelle_fluor_rollup",
]].rename(columns={
    "fish_code": "Fish",
    "birthday": "Birthday",
    "genotype_basecode_code": "Genotype basecodes",
    "genotype_transgene_allele_code": "Genotype allele code",
    "treatment_code": "Treatment code",
    "treatments_and_transgenes": "Tx + transgenes",
    "all_fluor_tag_rollup": "Tx → fluor::tag(pos)",
    "all_organelle_fluor_rollup": "Tx → organelle-fluor",
    "n_tanks": "# tanks",
})

fish_edited = st.data_editor(
    fish_view,
    hide_index=True,
    use_container_width=True,
    column_config={
        fish_sel_col: st.column_config.CheckboxColumn("✓", default=False),
        "Birthday":   st.column_config.DateColumn("Birthday", disabled=True),
        "# tanks":    st.column_config.NumberColumn("# tanks", disabled=True, format="%d"),
        "Genotype basecodes": st.column_config.TextColumn("Genotype basecodes", disabled=True),
        "Genotype allele code": st.column_config.TextColumn("Genotype allele code", disabled=True),
        "Treatment code": st.column_config.TextColumn("Treatment code", disabled=True),
        "Tx + transgenes": st.column_config.TextColumn("Tx + transgenes", disabled=True, width="large"),
        "Tx → fluor::tag(pos)": st.column_config.TextColumn("Tx → fluor::tag(pos)", disabled=True, width="large"),
        "Tx → organelle-fluor": st.column_config.TextColumn("Tx → organelle-fluor", disabled=True, width="large"),
    },
    key="manage_tank_status_fish_grid_v11",
)

fish_mask = fish_edited.get(fish_sel_col, pd.Series(False, index=fish_edited.index)).fillna(False).astype(bool)
selected_fish_codes = fish_edited.loc[fish_mask, "Fish"].astype(str).tolist()
selected_fish = selected_fish_codes[0] if selected_fish_codes else None

if not selected_fish:
    st.caption("Select a fish above to view and manage its tanks.")
    st.stop()

st.caption(f"Selected fish: {selected_fish}")

# ── Step 2 — Tanks for selected fish ─────────────────────────────────────────
st.subheader(f"2) Tanks for fish {selected_fish}")

tanks_df = _load_tanks_for_fish(selected_fish)

if tanks_df.empty:
    st.info("No tanks exist for this fish yet.")
    selected_ids: List[str] = []
else:
    t_sel_col = "✓ Select tank"
    tank_grid = tanks_df.copy()
    if t_sel_col not in tank_grid.columns:
        tank_grid.insert(0, t_sel_col, False)

    tank_view = tank_grid[[
        t_sel_col,
        "id",
        "tank_code",
        "fish_code",
        "status",
        "created_at",
    ]].rename(columns={
        "id": "Tank ID",
        "tank_code": "Tank code",
        "fish_code": "Fish",
        "status": "Status",
        "created_at": "Created at",
    })

    tank_edited = st.data_editor(
        tank_view,
        hide_index=True,
        use_container_width=True,
        column_config={
            t_sel_col:        st.column_config.CheckboxColumn("✓", default=False),
            "Tank ID":        st.column_config.TextColumn("Tank ID", disabled=True),
            "Created at":     st.column_config.DatetimeColumn("Created at", disabled=True),
            "Status":         st.column_config.TextColumn("Status", disabled=True),
        },
        key="manage_tank_status_tanks_grid_v11",
    )
    tmask = tank_edited.get(t_sel_col, pd.Series(False, index=tank_edited.index)).fillna(False).astype(bool)
    selected_ids = tank_edited.loc[tmask, "Tank ID"].astype(str).tolist()
    st.caption(f"{len(selected_ids)} tank(s) selected")

# ── Step 3 — Bulk status + create tanks ──────────────────────────────────────
st.subheader("3) Bulk status updates & create tanks")

col_a, col_b = st.columns([2, 2])

with col_a:
    st.markdown("**Bulk status change**")
    new_status = st.selectbox("New status", options=_distinct_statuses(), index=_distinct_statuses().index("active"))
    if st.button("Apply to selected tanks", use_container_width=True, disabled=not selected_ids):
        n = _bulk_update_status(selected_ids, new_status)
        st.success(f"Updated status for {n} tank(s).")
        st.rerun()

with col_b:
    st.markdown("**Create new tanks for this fish**")
    n_new = st.number_input("How many new tanks?", min_value=1, max_value=50, value=3, step=1)
    if st.button(f"➕ Create {n_new} new tanks for {selected_fish}", use_container_width=True):
        new_df = _create_new_tanks_for_fish(selected_fish, int(n_new))
        if new_df.empty:
            st.warning("No tanks created (check fish selection).")
        else:
            st.success(f"Created {len(new_df)} new tank(s) for fish {selected_fish}.")
            st.rerun()

# ── Step 4 — Single tank summary (optional) ──────────────────────────────────
st.subheader("4) Single tank summary")
if not selected_ids:
    st.caption("Select a tank above to see its details.")
else:
    tank_id = selected_ids[0]
    row = tanks_df.loc[tanks_df["id"] == tank_id].iloc[0].to_dict()
    st.write(f"**Tank code:** {row.get('tank_code')}")
    st.write(f"**Status:** {row.get('status')}")
    st.write(f"**Created at:** {_safe(row.get('created_at'))}")