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
except Exception:  # pragma: no cover
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
st.title("🔎 Search Fish → Tanks")
st.caption(f"DB_URL = {os.getenv('DB_URL', '')}")


# ───────── engine helpers ─────────
@st.cache_resource(show_spinner=False)
def _cached_engine() -> Engine:
    url = os.getenv("DB_URL", "")
    # If DB_URL is missing (e.g. dev), fall back to direct engine helper
    if not url:
        return _direct_engine()
    return _create_engine()


def _get_engine() -> Engine:
    return _cached_engine()


# ───────── small helpers ─────────
def _normalize_q(q_raw: str | None) -> Optional[str]:
    q = (q_raw or "").strip()
    return q or None


def _coerce_strings(df: pd.DataFrame | None) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    for c in df.select_dtypes(include=["object", "string"]).columns:
        df[c] = df[c].astype("string").fillna("")
    return df


def _table_exists(schema: str, name: str) -> bool:
    sql = text(
        """
        SELECT EXISTS (
          SELECT 1
          FROM information_schema.tables
          WHERE table_schema = :s
            AND table_name   = :t
        )
        """
    )
    with _get_engine().begin() as cx:
        return bool(cx.execute(sql, {"s": schema, "t": name}).scalar())


# ───────── data loaders ─────────
def _load_fish_overview(q: Optional[str], limit: int) -> pd.DataFrame:
    """
    v8 fish overview built directly from:

      - public.fish_instance
      - public.join_fish_transgene_alleles
      - public.transgene_alleles

    Genotype fields are derived rollups; there is no v_fish_overview view anymore.
    """
    sql = text(
        """
        WITH base AS (
          SELECT
            f.id,
            f.fish_code,
            f.nickname,
            f.genetic_background,
            f.line_building_stage,
            f.birthday,
            f.created_at
          FROM public.fish_instance f
        ),
        alleles AS (
          SELECT
            jfta.fish_id,
            string_agg(
              DISTINCT jfta.transgene_base_code,
              ', ' ORDER BY jfta.transgene_base_code
            ) AS genotype_base_codes,
            string_agg(
              'Tg(' || jfta.transgene_base_code || ')' ||
              COALESCE(
                NULLIF(ta.allele_name, ''),
                'gu' || jfta.allele_number::text
              ),
              '; ' ORDER BY jfta.transgene_base_code, jfta.allele_number
            ) AS genotype_alleles_pretty
          FROM public.join_fish_transgene_alleles jfta
          LEFT JOIN public.transgene_alleles ta
            ON ta.transgene_base_code = jfta.transgene_base_code
           AND ta.allele_number       = jfta.allele_number
          GROUP BY jfta.fish_id
        ),
        joined AS (
          SELECT
            b.id,
            b.fish_code,
            b.nickname,
            b.genetic_background,
            b.line_building_stage,
            b.birthday,
            b.created_at,
            a.genotype_base_codes,
            a.genotype_alleles_pretty,
            a.genotype_alleles_pretty AS genotype_pretty,
            NULL::text AS genotype_fluors,
            COALESCE(a.genotype_base_codes, '') AS all_base_codes,
            NULL::text AS all_fluors
          FROM base b
          LEFT JOIN alleles a ON a.fish_id = b.id
        )
        SELECT *
        FROM joined
        WHERE (
          :q IS NULL
          OR fish_code                        ILIKE :ql
          OR COALESCE(nickname,'')           ILIKE :ql
          OR COALESCE(genetic_background,'') ILIKE :ql
          OR COALESCE(line_building_stage,'')ILIKE :ql
          OR COALESCE(genotype_pretty,'')    ILIKE :ql
          OR COALESCE(genotype_alleles_pretty,'') ILIKE :ql
          OR COALESCE(genotype_base_codes,'')     ILIKE :ql
          OR COALESCE(all_base_codes,'')          ILIKE :ql
          OR COALESCE(all_fluors,'')              ILIKE :ql
        )
        ORDER BY created_at DESC NULLS LAST, fish_code
        LIMIT :lim
        """
    )

    params = {
        "q": q,
        "ql": f"%{q}%" if q else None,
        "lim": int(limit),
    }
    with _get_engine().begin() as cx:
        df = pd.read_sql(sql, cx, params=params)
    return _coerce_strings(df)


def _load_tanks_for_codes(codes: List[str]) -> pd.DataFrame:
    """
    Given a list of fish_codes, return active tanks from v_tanks if present,
    otherwise from tanks (with a regex to extract fish_code from tank_code).
    """
    codes = [c for c in (codes or []) if c]
    if not codes:
        return pd.DataFrame(
            columns=["fish_code", "tank_code", "status", "created_at", "container_id"]
        )

    use_view = _table_exists("public", "v_tanks")
    src_table = "public.v_tanks" if use_view else "public.tanks"
    id_col = "tank_uuid" if use_view else "id"

    sql = text(
        f"""
        SELECT
          v.{id_col}::text  AS container_id,
          v.tank_code::text AS tank_code,
          COALESCE(CAST(v.status AS text), ''::text) AS status,
          -- extract fish_code from tank_code if present, else leave empty
          regexp_replace(v.tank_code, '^.*\\(([^)]+)\\).*$', '\\1')::text AS fish_code,
          v.created_at::timestamptz AS created_at
        FROM {src_table} v
        WHERE regexp_replace(v.tank_code, '^.*\\(([^)]+)\\).*$', '\\1') = ANY(:codes)
        ORDER BY v.created_at ASC, v.tank_code ASC
        """
    )

    with _get_engine().begin() as cx:
        df = pd.read_sql(sql, cx, params={"codes": codes})
    return _coerce_strings(df)


def _fetch_enriched_for_containers(container_ids: List[str]) -> pd.DataFrame:
    """
    Given a list of tank container UUIDs, return enriched tank records including
    genotype/transgene text pulled from the fish overview logic.
    """
    ids = [x for x in (container_ids or []) if x]
    if not ids:
        return pd.DataFrame()

    use_view = _table_exists("public", "v_tanks")
    src_table = "public.v_tanks" if use_view else "public.tanks"
    id_col = "tank_uuid" if use_view else "id"

    sql = text(
        f"""
        WITH picked AS (
          SELECT unnest(:ids)::uuid AS container_id
        ),
        vt AS (
          SELECT
            v.{id_col}::uuid                           AS tank_id,
            v.tank_code::text                          AS tank_code,
            regexp_replace(v.tank_code, '^.*\\(([^)]+)\\).*$', '\\1')::text AS fish_code,
            COALESCE(CAST(v.status AS text), ''::text) AS status,
            v.created_at::timestamptz                  AS created_at,
            split_part(v.tank_code, '#', 2)            AS tank_num
          FROM {src_table} v
        ),
        fish_base AS (
          SELECT
            f.id,
            f.fish_code,
            f.nickname,
            f.genetic_background,
            f.line_building_stage,
            f.birthday,
            f.created_at
          FROM public.fish_instance f
        ),
        alleles AS (
          SELECT
            jfta.fish_id,
            string_agg(
              DISTINCT jfta.transgene_base_code,
              ', ' ORDER BY jfta.transgene_base_code
            ) AS genotype_base_codes,
            string_agg(
              'Tg(' || jfta.transgene_base_code || ')' ||
              COALESCE(
                NULLIF(ta.allele_name, ''),
                'gu' || jfta.allele_number::text
              ),
              '; ' ORDER BY jfta.transgene_base_code, jfta.allele_number
            ) AS genotype_alleles_pretty
          FROM public.join_fish_transgene_alleles jfta
          LEFT JOIN public.transgene_alleles ta
            ON ta.transgene_base_code = jfta.transgene_base_code
           AND ta.allele_number       = jfta.allele_number
          GROUP BY jfta.fish_id
        ),
        fish_joined AS (
          SELECT
            b.id,
            b.fish_code,
            b.nickname,
            b.genetic_background,
            b.line_building_stage,
            b.birthday,
            a.genotype_base_codes,
            a.genotype_alleles_pretty,
            a.genotype_alleles_pretty AS genotype_pretty
          FROM fish_base b
          LEFT JOIN alleles a ON a.fish_id = b.id
        )
        SELECT
          p.container_id::text AS container_id,
          vt.tank_code,
          vt.status,
          vt.fish_code,
          fj.nickname            AS name,
          fj.nickname            AS nickname,
          ''::text               AS alias,
          CASE
            WHEN vt.tank_num IS NOT NULL AND vt.tank_num <> ''
              THEN 'TANK(' || vt.fish_code || ')#' || vt.tank_num
              ELSE vt.tank_code
          END AS tank_display,
          fj.genotype_pretty     AS genotype,
          fj.genotype_alleles_pretty AS transgene_pretty,
          fj.genotype_base_codes AS genotype_base_codes,
          fj.genetic_background,
          fj.line_building_stage AS stage,
          fj.birthday            AS dob
        FROM picked p
        JOIN vt ON vt.tank_id = p.container_id
        LEFT JOIN fish_joined fj ON fj.fish_code = vt.fish_code
        ORDER BY vt.created_at ASC, vt.tank_code ASC
        """
    ).bindparams(bindparam("ids", type_=ARRAY(UUID(as_uuid=True))))

    with _get_engine().begin() as cx:
        df = pd.read_sql(sql, cx, params={"ids": ids})
    return _coerce_strings(df)


# ───────── main page ─────────
def main() -> None:
    # ── filters ──
    with st.container():
        c1, c2 = st.columns([3, 1])
        with c1:
            q_raw = st.text_input(
                "Search (code / nickname / background / genotype / alleles / fluors)",
                "",
            )
        with c2:
            limit = int(
                st.number_input(
                    "Limit",
                    min_value=1,
                    max_value=5000,
                    value=500,
                    step=100,
                )
            )

    q = _normalize_q(q_raw)

    # ── fish table ──
    df = _load_fish_overview(q, limit)
    if df.empty:
        st.info("No fish match your search.")
        return

    st.subheader(f"Fish ({len(df)} row(s))")
    table = df.copy()
    table.insert(0, "✓ Select", False)

    fish_table = st.data_editor(
        table,
        key="fish_table_v8",
        width="stretch",
        hide_index=True,
    )
    

    # selected fish
    selected = (
        fish_table.loc[fish_table["✓ Select"]].copy()
        if isinstance(fish_table, pd.DataFrame) and "✓ Select" in fish_table.columns
        else pd.DataFrame()
    )

    st.subheader("Export")
    st.caption(f"Selected fish: {len(selected)}")

    # Download current fish table
    st.download_button(
        "⬇︎ Download current fish table (CSV)",
        data=df.to_csv(index=False).encode("utf-8"),
        file_name=f"fish_overview_{len(df)}_rows.csv",
        type="secondary",
        use_container_width=True,
    )

    # Optional pivot of selected fish fields
    show_pivot = st.checkbox("Show pivot of selected fish fields", value=False)
    if show_pivot:
        if selected.empty:
            st.info("Select at least one fish to see pivoted fields.")
        else:
            id_cols = []
            for c in ("fish_code", "id"):
                if c in selected.columns:
                    id_cols.append(c)
            value_cols = [c for c in selected.columns if c not in id_cols + ["✓ Select"]]

            tidy = (
                selected[id_cols + value_cols]
                .melt(
                    id_vars=id_cols,
                    value_vars=value_cols,
                    var_name="field",
                    value_name="value",
                )
                .sort_values(id_cols + ["field"])
                .reset_index(drop=True)
            )

            st.subheader("Field pivot for selected fish")
            st.dataframe(tidy, width="stretch", hide_index=True)
            st.download_button(
                "⬇︎ Download fish field pivot (CSV)",
                data=tidy.to_csv(index=False).encode("utf-8"),
                file_name=f"fish_field_pivot_{utc_now().strftime('%Y%m%d_%H%M%S')}.csv",
                type="secondary",
                use_container_width=True,
            )

    # ── tanks for selected fish ──
    st.subheader("Tanks for selected fish")
    selected_codes = (
        selected["fish_code"].dropna().astype(str).tolist()
        if not selected.empty and "fish_code" in selected.columns
        else []
    )

    if not selected_codes:
        st.info("Select at least one fish above to see tanks.")
        return

    tdf = _load_tanks_for_codes(selected_codes)
    if tdf.empty:
        st.info("No tanks found for selected fish.")
        return

    tview = tdf.copy()
    tview.insert(0, "✓ Print", False)

    tanks_table = st.data_editor(
        tview,
        key="tank_table_v8",
        width="stretch",
        hide_index=True,
    )

    chosen = (
        tanks_table.loc[tanks_table["✓ Print"]]
        if isinstance(tanks_table, pd.DataFrame) and "✓ Print" in tanks_table.columns
        else pd.DataFrame()
    )

    st.caption(f"Selected tanks: {len(chosen)}")

    if not chosen.empty:
        ids = chosen["container_id"].astype(str).tolist()
        edf = _fetch_enriched_for_containers(ids)
        if not edf.empty:
            st.subheader("Enriched tank field pivot")
            id_cols = [c for c in ("tank_code", "container_id") if c in edf.columns]
            value_cols = [c for c in edf.columns if c not in id_cols]

            tidy_tanks = (
                edf[id_cols + value_cols]
                .melt(
                    id_vars=id_cols,
                    value_vars=value_cols,
                    var_name="field",
                    value_name="value",
                )
                .sort_values(id_cols + ["field"])
                .reset_index(drop=True)
            )

            st.dataframe(tidy_tanks, width="stretch", hide_index=True)
            st.download_button(
                "⬇︎ Download tank field pivot (CSV)",
                data=tidy_tanks.to_csv(index=False).encode("utf-8"),
                file_name=f"tanks_field_pivot_{utc_now().strftime('%Y%m%d_%H%M%S')}.csv",
                type="secondary",
                use_container_width=True,
            )


if __name__ == "__main__":  # pragma: no cover
    main()