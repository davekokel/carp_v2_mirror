from __future__ import annotations

import os
import pathlib
import sys
from typing import List, Optional, Dict, Any

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
    page_title="CARP — Overview: Tank pairs",
    page_icon="🔍",
    layout="wide",
)
st.title("🔍 Overview: Tank pairs")


# ───────── helpers ─────────
def _eng() -> Engine:
    return _engine()


def _cols(schema: str, table: str) -> List[str]:
    sql = text(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = :s AND table_name = :t
        ORDER BY ordinal_position
        """
    )
    with _eng().begin() as cx:
        df = pd.read_sql(sql, cx, params={"s": schema, "t": table})
    return df["column_name"].tolist()


def _assert_table(schema: str, table: str) -> None:
    sql = text(
        """
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = :s AND table_name = :t
        """
    )
    with _eng().begin() as cx:
        df = pd.read_sql(sql, cx, params={"s": schema, "t": table})
    if df.empty:
        raise RuntimeError(f"Required table {schema}.{table} is missing.")


def _discover_tanks_fish_fk_col() -> str:
    """
    Return the column in public.tanks that FK-references public.fish_instance(id).
    Require exactly one such column; error if 0 or >1.
    """
    sql = text(
        """
        WITH fk AS (
          SELECT
            con.oid,
            con.conrelid  AS tbl_oid,
            con.confrelid AS ref_oid,
            con.conkey    AS fk_cols
          FROM pg_constraint con
          WHERE con.contype='f'
            AND con.conrelid='public.tanks'::regclass
            AND con.confrelid='public.fish_instance'::regclass
        )
        SELECT a.attname AS fk_col
        FROM fk
        JOIN LATERAL unnest(fk.fk_cols) WITH ORDINALITY k(attnum, ord) ON TRUE
        JOIN pg_attribute a ON a.attrelid=fk.tbl_oid AND a.attnum=k.attnum
        ORDER BY ord
        """
    )
    with _eng().begin() as cx:
        df = pd.read_sql(sql, cx)

    if df.empty:
        raise RuntimeError(
            "No foreign key from public.tanks to public.fish_instance(id) was found."
        )
    cols = df["fk_col"].astype(str).tolist()
    uniq = sorted(set(cols))
    if len(uniq) != 1:
        raise RuntimeError(
            "Multiple FK columns in public.tanks reference public.fish_instance(id); "
            f"columns: {uniq}"
        )
    return uniq[0]


def _tank_pair_parent_cols() -> Dict[str, str]:
    cols = _cols("public", "tank_pairs")
    for mom, dad in (("mother_tank_id", "father_tank_id"), ("tank_id_mother", "tank_id_father")):
        if mom in cols and dad in cols:
            return {"mom": mom, "dad": dad}
    raise RuntimeError(
        "public.tank_pairs must have mother/father UUID columns. "
        f"Expected (mother_tank_id,father_tank_id) or (tank_id_mother,tank_id_father). Found: {cols}"
    )


def _norm(s: str | None) -> Optional[str]:
    s = (s or "").strip()
    return s or None


# ───────── schema sanity check once ─────────
@st.cache_data(show_spinner=False)
def _schema_info() -> Dict[str, Any]:
    for t in ("fish_instance", "tanks", "tank_pairs"):
        _assert_table("public", t)

    fish_cols = _cols("public", "fish_instance")
    for required in ("id", "fish_code"):
        if required not in fish_cols:
            raise RuntimeError(f"public.fish_instance must have column '{required}'. Found: {fish_cols}")

    tank_cols = _cols("public", "tanks")
    for required in ("id", "tank_code", "status", "created_at"):
        if required not in tank_cols:
            raise RuntimeError(f"public.tanks must have column '{required}'. Found: {tank_cols}")

    fk_col = _discover_tanks_fish_fk_col()
    if fk_col not in tank_cols:
        raise RuntimeError(f"FK column '{fk_col}' not found in public.tanks. Found: {tank_cols}")

    tp_parents = _tank_pair_parent_cols()

    return {
        "fish": {"id": "id", "code": "fish_code"},
        "tanks": {"id": "id", "code": "tank_code", "status": "status", "created": "created_at", "fish_fk": fk_col},
        "tank_pairs": tp_parents,
    }


# ───────── query: tank pair overview (no legacy views) ─────────
def load_tank_pairs(q: Optional[str], limit: int) -> pd.DataFrame:
    S = _schema_info()
    f, t, tp = S["fish"], S["tanks"], S["tank_pairs"]

    sql = text(
        f"""
        SELECT
          tp.id::text        AS tank_pair_id,
          tp.tank_pair_code,
          tp.created_at,
          tp.active_from,
          mt.{t['code']}     AS mother_tank_code,
          mf.{f['code']}     AS mother_fish_code,
          ft.{t['code']}     AS father_tank_code,
          ff.{f['code']}     AS father_fish_code
        FROM public.tank_pairs tp
        JOIN public.tanks mt ON mt.{t['id']} = tp.{tp['mom']}
        JOIN public.tanks ft ON ft.{t['id']} = tp.{tp['dad']}
        JOIN public.fish_instance mf ON mf.{f['id']} = mt.{t['fish_fk']}
        JOIN public.fish_instance ff ON ff.{f['id']} = ft.{t['fish_fk']}
        WHERE (:q IS NULL)
           OR (
                tp.tank_pair_code              ILIKE :ql
             OR mt.{t['code']}                 ILIKE :ql
             OR ft.{t['code']}                 ILIKE :ql
             OR mf.{f['code']}                 ILIKE :ql
             OR ff.{f['code']}                 ILIKE :ql
           )
        ORDER BY tp.created_at DESC NULLS LAST, tp.tank_pair_code
        LIMIT :lim
        """
    )

    qn = _norm(q)
    params = {
        "q": qn if qn else None,
        "ql": f"%{qn}%" if qn else None,
        "lim": int(limit),
    }

    with _eng().begin() as cx:
        df = pd.read_sql(sql, cx, params=params)
    for c in df.select_dtypes(include=["object", "string"]).columns:
        df[c] = df[c].astype("string").fillna("")
    return df


# ───────── UI ─────────
with st.form("tank_pair_filters", clear_on_submit=False):
    c1, c2 = st.columns([3, 1])
    with c1:
        q_raw = st.text_input(
            "Search (tank_pair_code / tank_code / fish_code)",
            "",
        )
    with c2:
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

df = load_tank_pairs(q_raw, lim)

if df.empty:
    st.info("No tank pairs found for current filters.")
else:
    st.caption(f"{len(df)} tank_pair(s)")
    st.data_editor(
        df,
        key="tank_pairs_overview_v8",
        hide_index=True,
        use_container_width=True,
        num_rows="fixed",
        column_config={
            "tank_pair_id":     st.column_config.TextColumn("ID", disabled=True),
            "tank_pair_code":   st.column_config.TextColumn("Tank pair code", disabled=True),
            "mother_tank_code": st.column_config.TextColumn("Mother tank", disabled=True),
            "mother_fish_code": st.column_config.TextColumn("Mother fish", disabled=True),
            "father_tank_code": st.column_config.TextColumn("Father tank", disabled=True),
            "father_fish_code": st.column_config.TextColumn("Father fish", disabled=True),
            "created_at":       st.column_config.DatetimeColumn("Created at", disabled=True),
            "active_from":      st.column_config.DatetimeColumn("Active from", disabled=True),
        },
    )

    st.download_button(
        "⬇︎ Download tank_pairs overview (CSV)",
        data=df.to_csv(index=False).encode("utf-8"),
        file_name="tank_pairs_overview.csv",
        type="secondary",
        mime="text/csv",
    )
