from __future__ import annotations
import os, sys, pathlib
from typing import Optional

import pandas as pd
import streamlit as st
from sqlalchemy import text
from sqlalchemy.engine import Engine

# repo root on sys.path
ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from carp_app.ui.auth_gate import require_auth
from carp_app.ui.email_otp_gate import require_email_otp
try:
    from carp_app.ui.auth_gate import require_app_unlock
except Exception:
    def require_app_unlock(): ...
from carp_app.ui.lib.app_ctx import get_engine as _create_engine
from carp_app.lib.time import utc_now


# ───────── auth & page ─────────
sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(
    page_title="CARP — v11 Treatments Overview",
    page_icon="🧪",
    layout="wide",
)
st.title("🧪 v11 Treatments Overview — mixes + markers")


# ───────── engine helper ─────────
@st.cache_resource(show_spinner=False)
def get_engine() -> Engine:
    return _create_engine()


# ───────── data loader ─────────
@st.cache_data(show_spinner=True)
def load_treatments(
    _engine: Engine,
    text_filter: str,
    row_limit: int,
) -> pd.DataFrame:
    sql = text(
        """
        SELECT
          t.treat_code                                   AS treatment_code,
          t.kind_code,
          t.treat_text,
          t.notes,
          t.created_at,
          string_agg(DISTINCT tm.mix_code, ', ' ORDER BY tm.mix_code)
            AS mix_codes,
          string_agg(DISTINCT c.base_code, ', ' ORDER BY c.base_code)
            AS genotype_basecode_code,
          NULL::text
            AS genotype_transgene_allele_code,
          string_agg(DISTINCT c.base_code, ', ' ORDER BY c.base_code)
            AS treatments_and_transgenes,
          string_agg(DISTINCT co.fusion_pretty, ', ' ORDER BY co.fusion_pretty)
            AS all_fluor_tag_rollup,
          string_agg(DISTINCT co.organelle_fluors, ', ' ORDER BY co.organelle_fluors)
            AS all_organelle_fluor_rollup
        FROM public.treatments t
        LEFT JOIN public.treatment_mixes tm
          ON tm.treatment_id = t.id
        LEFT JOIN public.treatment_mix_constructs tmc
          ON tmc.mix_id = tm.id
        LEFT JOIN public.constructs c
          ON c.id = tmc.construct_id
        LEFT JOIN public.v10_constructs_overview co
          ON co.construct_code = c.base_code
        GROUP BY
          t.treat_code,
          t.kind_code,
          t.treat_text,
          t.notes,
          t.created_at
        ORDER BY t.treat_code
        LIMIT :lim
        """
    )

    with _engine.begin() as cx:
        df = pd.read_sql(sql, cx, params={"lim": int(row_limit)})

    # text filter over main semantic fields
    text_filter = (text_filter or "").strip()
    if text_filter:
        f = text_filter.lower()

        def _match(row) -> bool:
            haystack = " ".join(
                str(row.get(col, "")) for col in [
                    "treatment_code",
                    "kind_code",
                    "treat_text",
                    "genotype_basecode_code",
                    "treatments_and_transgenes",
                    "all_fluor_tag_rollup",
                    "all_organelle_fluor_rollup",
                ]
            ).lower()
            return f in haystack

        mask = df.apply(_match, axis=1)
        df = df.loc[mask].reset_index(drop=True)

    return df


# ───────── controls ─────────
engine = get_engine()

col_filter, col_limit, col_meta = st.columns([4, 1, 2])

with col_filter:
    text_filter = st.text_input(
        "Search (treatment / basecode / markers)",
        value="",
        key="v11_treatments_text_filter",
        placeholder="e.g. T-LEGACY-014, PDQM-005, halo, H2B…",
    )

with col_limit:
    row_limit = st.number_input(
        "Row limit",
        min_value=10,
        max_value=5000,
        value=500,
        step=10,
        key="v11_treatments_row_limit",
    )

with col_meta:
    st.write("Now:", utc_now().isoformat(timespec="seconds"))
    st.caption("Treatments are defined at the mix level; markers roll up from constructs.")

df = load_treatments(
    _engine=engine,
    text_filter=text_filter,
    row_limit=int(row_limit),
)

st.markdown(f"**{len(df)}** treatment row(s)")

if df.empty:
    st.info("No treatments matched the current filters.")
else:
    # Standard 6 v11 fields + useful context
    cols = [
        "treatment_code",
        "kind_code",
        "treat_text",
        "mix_codes",
        "genotype_basecode_code",
        "genotype_transgene_allele_code",
        "treatments_and_transgenes",
        "all_fluor_tag_rollup",
        "all_organelle_fluor_rollup",
        "notes",
        "created_at",
    ]
    cols = [c for c in cols if c in df.columns]
    df_display = df[cols].copy()

    st.data_editor(
        df_display,
        height=600,
        use_container_width=True,
        num_rows="fixed",
        hide_index=True,
        key="v11_treatments_overview",
    )

    st.download_button(
        "⬇︎ Download treatments overview (CSV)",
        data=df_display.to_csv(index=False).encode("utf-8"),
        file_name="v11_treatments_overview.csv",
        type="secondary",
        mime="text/csv",
    )