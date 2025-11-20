# carp_app/ui/pages/110_🔎_overview_fish.py
from __future__ import annotations

import os
import sys
import pathlib
from typing import Optional

import pandas as pd
import streamlit as st
from sqlalchemy import text
from sqlalchemy.engine import Engine

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
st.title("🔎 Search Fish → Tanks")


# ───────── engine helpers ─────────
@st.cache_resource(show_spinner=False)
def _cached_engine() -> Engine:
    url = os.getenv("DB_URL", "")
    if not url:
        return _direct_engine()
    return _create_engine()


def _get_engine() -> Engine:
    return _cached_engine()


# ───────── helpers ─────────
def _normalize_q(q_raw: str | None) -> Optional[str]:
    q = (q_raw or "").strip()
    return q or None


def _coerce_strings(df: pd.DataFrame | None) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    for c in df.select_dtypes(include=["object", "string"]).columns:
        df[c] = df[c].astype("string").fillna("")
    return df


# ───────── v8 fish overview query ─────────
def _load_fish_overview(q: Optional[str], limit: int) -> pd.DataFrame:
    """
    v8 fish overview built from:

      - public.fish_instance
      - public.genotype_transgene_alleles
      - public.transgene_alleles

    using fish_instance.standard_genotype_code as the link into genotypes.
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
            f.created_at,
            f.standard_genotype_code AS genotype_code
          FROM public.fish_instance f
        ),
        alleles AS (
          SELECT
            gta.genotype_code,
            string_agg(
              DISTINCT gta.transgene_base_code,
              ', ' ORDER BY gta.transgene_base_code
            ) AS genotype_base_codes,
            string_agg(
              'Tg(' || gta.transgene_base_code || ')' ||
              COALESCE(
                NULLIF(ta.allele_name, ''),
                'gu' || gta.allele_number::text
              ),
              '; ' ORDER BY gta.transgene_base_code, gta.allele_number
            ) AS genotype_alleles_pretty
          FROM public.genotype_transgene_alleles gta
          LEFT JOIN public.transgene_alleles ta
            ON ta.transgene_base_code = gta.transgene_base_code
           AND ta.allele_number       = gta.allele_number
          GROUP BY gta.genotype_code
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
            b.genotype_code,
            a.genotype_base_codes,
            a.genotype_alleles_pretty,
            a.genotype_alleles_pretty AS genotype_pretty,
            NULL::text AS genotype_fluors,
            COALESCE(a.genotype_base_codes, '') AS all_base_codes,
            NULL::text AS all_fluors
          FROM base b
          LEFT JOIN alleles a
            ON a.genotype_code = b.genotype_code
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

    qnorm = _normalize_q(q)
    params = {
        "q": qnorm,
        "ql": f"%{qnorm}%" if qnorm else None,
        "lim": int(limit),
    }

    with _get_engine().begin() as cx:
        df = pd.read_sql(sql, cx, params=params)

    return _coerce_strings(df)


# ───────── page body ─────────
def main() -> None:
    st.caption(f"DB_URL = {os.getenv('DB_URL', '')}")

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
    df = _load_fish_overview(q, limit)

    if df.empty:
        st.info("No fish match your search.")
        return

    # ── main fish table ──
    st.subheader(f"Fish ({len(df)} row(s))")

    view = df.copy()
    view.insert(0, "✓ Select", False)

    fish_view = st.data_editor(
        view,
        key="overview_fish_v8",
        width="stretch",
        hide_index=True,
        column_config={
            "✓ Select":                    st.column_config.CheckboxColumn("✓", default=False),
            "fish_code":                   st.column_config.TextColumn("Fish code", disabled=True),
            "nickname":                    st.column_config.TextColumn("Nickname", disabled=True),
            "genetic_background":          st.column_config.TextColumn("Background", disabled=True),
            "line_building_stage":         st.column_config.TextColumn("Line stage", disabled=True),
            "birthday":                    st.column_config.DateColumn("Birthday", disabled=True),
            "genotype_code":               st.column_config.TextColumn("Genotype code", disabled=True),
            "genotype_pretty":             st.column_config.TextColumn("Genotype (pretty)", disabled=True),
            "genotype_alleles_pretty":     st.column_config.TextColumn("Alleles (pretty)", disabled=True),
            "genotype_base_codes":         st.column_config.TextColumn("Genotype base codes", disabled=True),
            "genotype_fluors":             st.column_config.TextColumn("Genotype fluors", disabled=True),
            "all_base_codes":              st.column_config.TextColumn("All base codes", disabled=True),
            "all_fluors":                  st.column_config.TextColumn("All fluors", disabled=True),
            "created_at":                  st.column_config.DatetimeColumn("Created at", disabled=True),
        },
    )

    # ───────── pivot for selected fish ─────────
    st.divider()
    st.subheader("Pivot: selected fish (expanded fields)")

    selected = (
        fish_view.loc[fish_view["✓ Select"] == True].copy()
        if isinstance(fish_view, pd.DataFrame) and "✓ Select" in fish_view.columns
        else pd.DataFrame()
    )

    if selected.empty:
        st.caption("Select one or more fish above to see a field-by-field pivot.")
    else:
        # identify id columns (kept as-is)
        id_cols: list[str] = []
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

        st.dataframe(tidy, hide_index=True, width="stretch")
        st.download_button(
            "⬇︎ Download field pivot for selected fish (CSV)",
            data=tidy.to_csv(index=False).encode("utf-8"),
            file_name=f"fish_field_pivot_{len(selected)}fish_{utc_now().strftime('%Y%m%d_%H%M%S')}.csv",
            type="secondary",
            use_container_width=True,
        )

    # ───────── export main table ─────────
    st.divider()
    st.subheader("Export")

    st.caption(f"Selected rows: {len(selected)}")

    st.download_button(
        "⬇︎ Download current fish table (CSV)",
        data=df.to_csv(index=False).encode("utf-8"),
        file_name=f"fish_overview_{len(df)}_rows_{utc_now().strftime('%Y%m%d_%H%M%S')}.csv",
        type="secondary",
        mime="text/csv",
        use_container_width=True,
    )


if __name__ == "__main__":
    main()