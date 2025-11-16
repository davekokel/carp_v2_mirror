# carp_app/ui/pages/110_🔎_overview_fish.py
from __future__ import annotations

import os
import sys
import pathlib
from typing import Optional, List

import pandas as pd
import streamlit as st
from sqlalchemy import text, bindparam
from sqlalchemy.engine import Engine
from sqlalchemy.dialects.postgresql import ARRAY, UUID

# ───────── repo path/bootstrap ─────────
ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from carp_app.lib.time import utc_now
from carp_app.ui.auth_gate import require_auth
from carp_app.ui.email_otp_gate import require_email_otp
try:
    from carp_app.ui.auth_gate import require_app_unlock
except Exception:
    def require_app_unlock():
        return None

from carp_app.ui.lib.page_engine import engine as _direct_engine
from carp_app.ui.lib.app_ctx import get_engine as _create_engine

# ───────── auth & page ─────────
sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(
    page_title="CARP — Search Fish → Tanks",
    page_icon="🔎",
    layout="wide",
)

@st.cache_resource(show_spinner=False)
def _cached_engine() -> Engine:
    # Use the same engine wiring as the rest of the app
    url = os.getenv("DB_URL", "")
    if not url:
        # Fallback to page_engine if DB_URL isn't set via app_ctx
        return _direct_engine()
    return _create_engine()

def _get_engine() -> Engine:
    return _cached_engine()

# ───────── helpers ─────────
def _normalize_q(q_raw: str) -> Optional[str]:
    q = (q_raw or "").strip()
    return q or None

def _coerce_strings(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    for c in df.select_dtypes(include=["object", "string"]).columns:
        df[c] = df[c].astype("string").fillna("")
    return df

def _table_exists(schema: str, table: str) -> bool:
    sql = text("""
      SELECT EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = :s AND table_name = :t
      )
    """)
    with _get_engine().begin() as cx:
        return bool(cx.execute(sql, {"s": schema, "t": table}).scalar())

# ───────── data loaders ─────────
def _load_fish_overview(q: Optional[str], limit: int) -> pd.DataFrame:
    """
    Load fish from v_fish_overview.

    v_fish_overview is the canonical fish view and is responsible for:
      - genotype_pretty      = Tg(base)allele_name (allele_name = 'gu' || allele_number)
      - transgene_canonical  = Tg(base)allele_name
      - transgene_nickname   = Tg(base)allele_nickname

    This page does not reimplement transgene logic; it only filters and displays.
    """
    sql = text("""
      SELECT *
      FROM public.v_fish_overview v
      WHERE (:q IS NULL)
         OR (
              v.fish_code_raw        ILIKE :q
           OR v.fish_code_display    ILIKE :q
           OR v.nickname             ILIKE :q
           OR v.genetic_background   ILIKE :q
           OR v.line_building_stage  ILIKE :q
           OR v.genotype_pretty      ILIKE :q
           OR v.transgene_canonical  ILIKE :q
           OR v.transgene_nickname   ILIKE :q
           OR v.markers              ILIKE :q
           OR v.fluors               ILIKE :q
           OR v.tags                 ILIKE :q
           OR v.fusions              ILIKE :q
         )
      ORDER BY v.created_at DESC NULLS LAST, v.fish_code_raw
      LIMIT :lim
    """)
    params = {"q": (f"%{q}%" if q else None), "lim": int(limit)}
    with _get_engine().begin() as cx:
        df = pd.read_sql(sql, cx, params=params)
    return _coerce_strings(df)

def _fetch_enriched_for_containers(container_ids: List[str]) -> pd.DataFrame:
    """
    Given a list of tank container UUIDs, return enriched tank records including:
      - genotype / transgene_pretty = v_fish_overview.genotype_pretty (canonical Tg(base)allele_name)
      - genotype_nickname           = v_fish_overview.transgene_nickname
    """
    ids = [x for x in (container_ids or []) if x]
    if not ids:
        return pd.DataFrame()

    use_view = _table_exists("public", "v_tanks")
    src_table = "public.v_tanks" if use_view else "public.tanks"
    id_col   = "tank_uuid" if use_view else "id"

    sql = text(f"""
      WITH picked AS (
        SELECT unnest(:ids) AS container_id
      ),
      vt AS (
        SELECT
            v.{id_col}::uuid AS tank_id,
            v.tank_code::text AS tank_code,
            regexp_replace(v.tank_code, '^.*\\(([^)]+)\\).*$', '\\1')::text AS fish_code,
            COALESCE(CAST(v.status AS text), ''::text) AS status,
            v.created_at::timestamptz AS created_at,
            split_part(v.tank_code, '#', 2) AS tank_num
        FROM {src_table} v
      ),
      vf AS (
        SELECT
            v.fish_code_raw              AS fish_code,
            COALESCE(v.nickname,'')      AS nickname,
            COALESCE(v.genetic_background,'') AS genetic_background,
            COALESCE(v.line_building_stage,'') AS stage,
            v.birthday::date             AS dob,
            COALESCE(v.genotype_pretty,'')     AS genotype,
            COALESCE(v.genotype_pretty,'')     AS transgene_pretty,
            COALESCE(v.transgene_nickname,'')  AS genotype_nickname
        FROM public.v_fish_overview v
      )
      SELECT
        p.container_id::text AS container_id,
        vt.tank_code,
        vt.status,
        vt.fish_code,
        vf.nickname AS name,
        vf.nickname AS nickname,
        ''::text    AS alias,
        CASE
          WHEN vt.tank_num IS NOT NULL AND vt.tank_num <> ''
            THEN 'TANK(' || vt.fish_code || ')#' || vt.tank_num
            ELSE vt.tank_code
        END AS tank_display,
        vf.genotype,
        vf.transgene_pretty,
        vf.genotype_nickname,
        vf.genetic_background,
        vf.stage,
        vf.dob
      FROM picked p
      JOIN vt ON vt.tank_id = p.container_id
      LEFT JOIN vf ON vf.fish_code = vt.fish_code
      ORDER BY vt.created_at ASC, vt.tank_code ASC
    """).bindparams(bindparam("ids", type_=ARRAY(UUID(as_uuid=True))))

    with _get_engine().begin() as cx:
        df = pd.read_sql(sql, cx, params={"ids": ids})
    return _coerce_strings(df)

def _load_tanks_for_codes(codes: List[str]) -> pd.DataFrame:
    if not codes:
        return pd.DataFrame(
            columns=["fish_code", "tank_code", "status", "created_at", "container_id"]
        )
    use_view = _table_exists("public", "v_tanks")
    src_table = "public.v_tanks" if use_view else "public.tanks"
    id_col   = "tank_uuid" if use_view else "id"

    sql = text(f"""
      SELECT
        v.{id_col}::text  AS container_id,
        v.tank_code::text AS tank_code,
        COALESCE(CAST(v.status AS text), ''::text) AS status,
        regexp_replace(v.tank_code, '^.*\\(([^)]+)\\).*$', '\\1')::text AS fish_code,
        v.created_at::timestamptz AS created_at
      FROM {src_table} v
      WHERE regexp_replace(v.tank_code, '^.*\\(([^)]+)\\).*$', '\\1') = ANY(:codes)
      ORDER BY v.created_at ASC, v.tank_code ASC
    """)
    with _get_engine().begin() as cx:
        df = pd.read_sql(sql, cx, params={"codes": codes})
    return _coerce_strings(df)

# ───────── page ─────────
def main():
    st.title("🔎 Search Fish → Tanks")
    st.caption(f"DB_URL = {os.getenv('DB_URL','')}")

    with st.container():
        c1, c2 = st.columns([3, 1])
        with c1:
            q_raw = st.text_input(
                "Search (code / nickname / background / genotype / alleles / fluors / tags)",
                "",
            )
        with c2:
            limit = int(
                st.number_input("Limit", min_value=1, max_value=5000, value=500, step=100)
            )
        q = _normalize_q(q_raw)

    df = _load_fish_overview(q, limit)
    if df.empty:
        st.info("No fish match your search.")
        return

    cols = [c for c in df.columns if c not in ("fish_code_raw",)]
    st.subheader(f"Fish ({len(df)} rows)")
    table = df[cols].copy()
    table.insert(0, "✓ Select", False)

    fish_table = st.data_editor(
        table,
        hide_index=True,
        width="stretch",
        key="fish_table_v8",
    )

    st.subheader("Tanks for selected fish")
    selected_codes = (
        fish_table.loc[fish_table["✓ Select"], "fish_code_display"]
        .dropna()
        .astype(str)
        .tolist()
        if isinstance(fish_table, pd.DataFrame) and "✓ Select" in fish_table.columns
        else []
    )
    if not selected_codes:
        st.info("Select at least one fish.")
        st.stop()

    tdf = _load_tanks_for_codes(selected_codes)
    if tdf.empty:
        st.info("No tanks for selected fish.")
        st.stop()

    tview = tdf.copy()
    tview.insert(0, "✓ Print", False)
    tanks_table = st.data_editor(
        tview,
        width="stretch",
        hide_index=True,
        key="tank_table",
    )

    chosen = (
        tanks_table.loc[tanks_table["✓ Print"] == True]
        if isinstance(tanks_table, pd.DataFrame) and "✓ Print" in tanks_table.columns
        else pd.DataFrame()
    )
    st.caption(f"{len(chosen)} tank(s) selected")

    if chosen.empty:
        st.stop()

    # Enrich selected tanks → edf
    ids = chosen["container_id"].astype(str).tolist()
    edf = _fetch_enriched_for_containers(ids)
    if edf.empty:
        st.info("No enriched tank data found.")
        st.stop()

    # ───────── Pivot view of all fields ─────────
    st.subheader("Pivot: fields linked to selected tank(s)")

    pivot_id_cols = [c for c in ["container_id", "tank_code"] if c in edf.columns]
    value_cols = [c for c in edf.columns if c not in pivot_id_cols]

    tidy = edf[pivot_id_cols + value_cols].melt(
        id_vars=pivot_id_cols,
        value_vars=value_cols,
        var_name="field",
        value_name="value",
    ).reset_index(drop=True)

    sort_keys = [k for k in ("tank_code", "field") if k in tidy.columns]
    tidy = tidy.sort_values(by=sort_keys or ["field"])

    st.dataframe(tidy, width="stretch", hide_index=True)
    st.download_button(
        "⬇︎ Download pivot (CSV)",
        data=tidy.to_csv(index=False).encode("utf-8"),
        file_name=f"tanks_field_pivot_{utc_now().strftime('%Y%m%d_%H%M%S')}.csv",
        type="secondary",
        width="stretch",
    )

if __name__ == "__main__":
    main()