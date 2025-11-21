# carp_app/ui/pages/180_🗓️_schedule_new_cross.py
from __future__ import annotations

import sys
import os
import pathlib
from datetime import date
from typing import List, Optional, Tuple, Dict, Any

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
    page_title="CARP — 🗓️ Schedule new cross",
    page_icon="🗓️",
    layout="wide",
)
st.title("🗓️ Schedule new cross")


# ───────── engine helper ─────────
def eng() -> Engine:
    return _engine()


def _norm(s: str | None) -> Optional[str]:
    s = (s or "").strip()
    return s or None


# ───────── tank pair list (for picker) ─────────
def list_tank_pairs(q: str, limit: int) -> pd.DataFrame:
    """
    Enriched tank pair list using v_fish_overview so humans can see
    genotype and basic fish info directly in the picker.
    """
    like = f"%{q.strip()}%" if q and q.strip() else None

    sql = text(
        """
        WITH tm AS (
          SELECT
            t.id::uuid      AS tank_id,
            t.tank_code     AS tank_code,
            f.fish_code     AS fish_code
          FROM public.tanks t
          JOIN public.fish_instance f
            ON f.id = t.fish_id
          WHERE lower(trim(t.status)) = 'active'
        ),
        mom AS (
          SELECT
            m.tank_id,
            m.tank_code,
            m.fish_code,
            vo.genotype_pretty AS genotype
          FROM tm m
          LEFT JOIN public.v_fish_overview vo
            ON vo.fish_code = m.fish_code
        ),
        dad AS (
          SELECT
            d.tank_id,
            d.tank_code,
            d.fish_code,
            vo.genotype_pretty AS genotype
          FROM tm d
          LEFT JOIN public.v_fish_overview vo
            ON vo.fish_code = d.fish_code
        ),
        pairs AS (
          SELECT
            tp.id::uuid        AS tank_pair_id,
            tp.tank_pair_code  AS tank_pair_code,
            tp.created_at      AS created_at,
            mom.fish_code      AS mom_fish_code,
            mom.tank_code      AS mom_tank_code,
            mom.genotype       AS mom_genotype,
            dad.fish_code      AS dad_fish_code,
            dad.tank_code      AS dad_tank_code,
            dad.genotype       AS dad_genotype
          FROM public.tank_pairs tp
          LEFT JOIN mom ON mom.tank_id = tp.mother_tank_id
          LEFT JOIN dad ON dad.tank_id = tp.father_tank_id
        )
        SELECT
          tank_pair_id,
          tank_pair_code,
          created_at,
          mom_fish_code,
          mom_tank_code,
          mom_genotype,
          dad_fish_code,
          dad_tank_code,
          dad_genotype
        FROM pairs
        WHERE (
          :q IS NULL
          OR tank_pair_code ILIKE :ql
          OR mom_tank_code  ILIKE :ql
          OR mom_fish_code  ILIKE :ql
          OR dad_tank_code  ILIKE :ql
          OR dad_fish_code  ILIKE :ql
        )
        ORDER BY created_at DESC NULLS LAST, tank_pair_code
        LIMIT :lim
        """
    )

    qn = _norm(q)
    params = {
        "q": qn if qn else None,
        "ql": like,
        "lim": int(limit),
    }

    with eng().begin() as cx:
        df = pd.read_sql(sql, cx, params=params)

    for col in df.select_dtypes(include=["object", "string"]).columns:
        df[col] = df[col].astype("string")
    return df


# ───────── cross + clutch upsert: ALWAYS create CR + CL together ─────────
def upsert_cross_and_clutch_for_tank_pair(tp_id: str, run_date: date) -> Tuple[str, str, str, str]:
    """
    Ensure there is exactly one cross AND one clutch for (tank_pair_id, run_date).

    - Cross:
        id            = new UUID (if needed)
        cross_run_code = 'CR-' || first 8 chars of id
    - Clutch:
        id          = new UUID (if needed)
        clutch_code = 'CL-' || first 8 chars of id

    Returns: (cross_id, cross_run_code, clutch_id, clutch_code)
    """
    d_str = str(run_date)

    with eng().begin() as cx:
        # 1) Upsert cross for (tank_pair_id, date)
        cross_sql = text(
            """
            WITH new_id AS (
              SELECT gen_random_uuid() AS id
            ),
            ins AS (
              INSERT INTO public.crosses (
                id,
                tank_pair_id,
                female_fish_id,
                male_fish_id,
                created_at,
                cross_run_code
              )
              SELECT
                new_id.id                         AS id,
                :tp_id                            AS tank_pair_id,
                mf.id                             AS female_fish_id,
                ff.id                             AS male_fish_id,
                CAST(:d AS date)                  AS created_at,
                'CR-' || left(new_id.id::text, 8) AS cross_run_code
              FROM new_id
              JOIN public.tank_pairs tp
                ON tp.id = :tp_id
              JOIN public.tanks mt
                ON mt.id = tp.mother_tank_id
              JOIN public.fish_instance mf
                ON mf.id = mt.fish_id
              JOIN public.tanks ft
                ON ft.id = tp.father_tank_id
              JOIN public.fish_instance ff
                ON ff.id = ft.fish_id
              WHERE NOT EXISTS (
                SELECT 1
                FROM public.crosses c
                WHERE c.tank_pair_id = :tp_id
                  AND DATE(c.created_at) = CAST(:d AS date)
              )
              RETURNING id, cross_run_code
            ),
            sel AS (
              SELECT id, cross_run_code
              FROM ins
              UNION ALL
              SELECT id, cross_run_code
              FROM public.crosses c
              WHERE c.tank_pair_id = :tp_id
                AND DATE(c.created_at) = CAST(:d AS date)
                AND NOT EXISTS (SELECT 1 FROM ins)
            )
            SELECT id, cross_run_code
            FROM sel
            LIMIT 1
            """
        )
        cross_row = cx.execute(cross_sql, {"tp_id": tp_id, "d": d_str}).fetchone()
        if not cross_row:
            raise RuntimeError("Failed to insert or locate cross for tank pair.")
        cross_id, cross_run_code = cross_row

        # 2) Upsert clutch for (cross_id, clutch_date)
        clutch_sql = text(
            """
            WITH new_id AS (
              SELECT gen_random_uuid() AS id
            ),
            ins AS (
              INSERT INTO public.clutches (
                id,
                clutch_code,
                cross_id,
                clutch_date
              )
              SELECT
                new_id.id                         AS id,
                'CL-' || left(new_id.id::text, 8) AS clutch_code,
                :cross_id                         AS cross_id,
                CAST(:d AS date)                  AS clutch_date
              FROM new_id
              WHERE NOT EXISTS (
                SELECT 1
                FROM public.clutches c
                WHERE c.cross_id = :cross_id
                  AND c.clutch_date = CAST(:d AS date)
              )
              RETURNING id, clutch_code
            ),
            sel AS (
              SELECT id, clutch_code
              FROM ins
              UNION ALL
              SELECT id, clutch_code
              FROM public.clutches c
              WHERE c.cross_id = :cross_id
                AND c.clutch_date = CAST(:d AS date)
                AND NOT EXISTS (SELECT 1 FROM ins)
            )
            SELECT id, clutch_code
            FROM sel
            LIMIT 1
            """
        )
        clutch_row = cx.execute(clutch_sql, {"cross_id": cross_id, "d": d_str}).fetchone()
        if not clutch_row:
            raise RuntimeError("Failed to insert or locate clutch for cross.")
        clutch_id, clutch_code = clutch_row

    return str(cross_id), str(cross_run_code), str(clutch_id), str(clutch_code)


# ───────── UI: tank pair picker + schedule cross+clutch ─────────
with st.form("tank_pair_filters", clear_on_submit=False):
    c1, c2 = st.columns([3, 1])
    with c1:
        q_raw = st.text_input(
            "Filter tank pairs (tank_pair_code / tank_code / fish_code)",
            "",
        )
    with c2:
        limit = int(
            st.number_input(
                "Row limit",
                min_value=10,
                max_value=2000,
                value=200,
                step=50,
            )
        )
    _ = st.form_submit_button("Apply")

pairs = list_tank_pairs(q_raw or "", limit)

if pairs.empty:
    st.info("No tank pairs match the current filters.")
    st.stop()

st.subheader("Step 1 — Select a tank pair")
view = pairs.copy()
view.insert(0, "✓", False)

grid = st.data_editor(
    view,
    key="tank_pairs_picker",
    hide_index=True,
    use_container_width=True,
    num_rows="fixed",
    column_order=[
        "✓",
        "tank_pair_code",
        "mom_fish_code",
        "mom_tank_code",
        "mom_genotype",
        "dad_fish_code",
        "dad_tank_code",
        "dad_genotype",
        "created_at",
    ],
    column_config={
        "✓":               st.column_config.CheckboxColumn("✓", default=False),
        "tank_pair_code":  st.column_config.TextColumn("Tank pair", disabled=True),
        "mom_fish_code":   st.column_config.TextColumn("Mother fish", disabled=True),
        "mom_tank_code":   st.column_config.TextColumn("Mother tank", disabled=True),
        "mom_genotype":    st.column_config.TextColumn("Mother genotype", disabled=True),
        "dad_fish_code":   st.column_config.TextColumn("Father fish", disabled=True),
        "dad_tank_code":   st.column_config.TextColumn("Father tank", disabled=True),
        "dad_genotype":    st.column_config.TextColumn("Father genotype", disabled=True),
        "created_at":      st.column_config.DatetimeColumn("Pair created at", disabled=True),
    },
)

sel = grid.loc[grid["✓"] == True] if "✓" in grid.columns else pd.DataFrame()
if sel.empty:
    st.info("Select a tank pair above to schedule a cross.")
    st.stop()

row = sel.iloc[0]
tp_id = row["tank_pair_id"]
tp_code = row["tank_pair_code"]

st.success(f"Selected tank pair: {tp_code}")

st.subheader("Step 2 — Choose cross date")
run_date = st.date_input("Cross date", value=date.today())

st.subheader("Step 3 — Save cross + clutch")

if st.button("💾 Schedule cross + clutch", type="primary", use_container_width=True):
    try:
        cross_id, cross_run_code, clutch_id, clutch_code = upsert_cross_and_clutch_for_tank_pair(tp_id, run_date)
        label = f"{tp_code} @ {run_date.isoformat()}"
        st.success(
            f"Cross scheduled: {cross_run_code} ({label}) (id={cross_id}); "
            f"Clutch created: {clutch_code} (id={clutch_id})"
        )
    except Exception as e:
        st.error(f"Schedule failed: {type(e).__name__}: {e}")
