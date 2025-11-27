from __future__ import annotations

import os
import pathlib
import sys
from datetime import datetime
from typing import Optional, Dict, Any

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

from carp_app.ui.lib.app_ctx import get_engine

# ───────── auth & page ─────────
sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(
    page_title="CARP — v11 Clutches overview",
    page_icon="🐣",
    layout="wide",
)
st.title("🐣 v11 Clutches overview")

# ───────── engine (cached) ─────────
@st.cache_resource(show_spinner=False)
def _eng() -> Engine:
    url = os.getenv("DB_URL")
    if not url:
        st.error("DB_URL is not set")
        st.stop()
    return get_engine()


def _norm(s: str | None) -> Optional[str]:
    s = (s or "").strip()
    return s or None


# ───────── filters ─────────
with st.form("clutch_filters_v11", clear_on_submit=False):
    c1, c2, c3 = st.columns([3, 2, 0.8])
    with c1:
        q_raw = st.text_input(
            "Search (clutch_code / genotype / source / treat codes)",
            "",
        )
    with c2:
        clutch_date_from_raw = st.text_input(
            "Clutch date from (YYYY-MM-DD, optional)",
            "",
        )
    with c3:
        lim = int(
            st.number_input(
                "Limit",
                min_value=50,
                max_value=5000,
                value=500,
                step=50,
            )
        )
    _ = st.form_submit_button("Apply")

q = _norm(q_raw)
clutch_date_from = _norm(clutch_date_from_raw)

# ───────── build WHERE for v11_clutch_star ─────────
where = ["1=1"]
params: Dict[str, Any] = {"lim": lim}

if q:
    params["ql"] = f"%{q}%"
    where.append(
        "("
        "  c.clutch_code   ILIKE :ql"
        " OR c.genotype    ILIKE :ql"
        " OR c.source_system ILIKE :ql"
        " OR c.treat_codes ILIKE :ql"
        ")"
    )

if clutch_date_from:
    try:
        dt = datetime.strptime(clutch_date_from, "%Y-%m-%d").date()
        params["clutch_date_from"] = dt.isoformat()
        where.append("c.clutch_date >= :clutch_date_from")
    except ValueError:
        st.warning("Clutch date from must be in YYYY-MM-DD format.")
        st.stop()

where_sql = " AND ".join(where)

sql = text(f"""
    SELECT
      c.clutch_id,
      c.clutch_code,
      c.clutch_date,
      c.genotype,
      c.source_system,
      c.n_imaging_slots,
      c.n_rois,
      c.treat_codes,
      c.kind_codes,
      c.mix_codes,
      c.fluor_codes,
      c.fluor_names,
      c.tag_codes
    FROM public.v11_clutch_star c
    WHERE {where_sql}
    ORDER BY c.clutch_date, c.clutch_code
    LIMIT :lim;
""")

try:
    with _eng().begin() as cx:
        df = pd.read_sql(sql, cx, params=params)
except Exception as e:
    st.error("Error querying v11_clutch_star.")
    st.exception(e)
    st.stop()

for c in df.select_dtypes(include=["object", "string"]).columns:
    df[c] = df[c].astype("string").fillna("")

st.caption(f"{len(df)} clutch row(s)")

# ───────── table ─────────
if df.empty:
    st.info("No clutches match the current filters.")
else:
    view = df.copy()
    view.insert(0, "✓ Select", False)

    st.data_editor(
        view,
        key="v11_clutches_overview",
        hide_index=True,
        use_container_width=True,
        num_rows="fixed",
        column_order=[
            "✓ Select",
            "clutch_code",
            "clutch_date",
            "genotype",
            "source_system",
            "n_imaging_slots",
            "n_rois",
            "treat_codes",
            "kind_codes",
            "mix_codes",
            "fluor_codes",
            "fluor_names",
            "tag_codes",
        ],
        column_config={
            "✓ Select":        st.column_config.CheckboxColumn("✓", default=False),
            "clutch_code":     st.column_config.TextColumn("Clutch", disabled=True),
            "clutch_date":     st.column_config.DateColumn("Clutch date", disabled=True),
            "genotype":        st.column_config.TextColumn("Genotype", disabled=True),
            "source_system":   st.column_config.TextColumn("Source", disabled=True),
            "n_imaging_slots": st.column_config.NumberColumn("# imaging slots", disabled=True),
            "n_rois":          st.column_config.NumberColumn("# ROIs", disabled=True),
            "treat_codes":     st.column_config.TextColumn("Treat codes", disabled=True),
            "kind_codes":      st.column_config.TextColumn("Kinds", disabled=True),
            "mix_codes":       st.column_config.TextColumn("Mix codes", disabled=True),
            "fluor_codes":     st.column_config.TextColumn("Fluor codes", disabled=True),
            "fluor_names":     st.column_config.TextColumn("Fluor names", disabled=True),
            "tag_codes":       st.column_config.TextColumn("Tag codes", disabled=True),
        },
    )

    st.download_button(
        "⬇︎ Download v11 clutch star (CSV)",
        data=df.to_csv(index=False).encode("utf-8"),
        file_name="v11_clutch_star_overview.csv",
        type="secondary",
        mime="text/csv",
    )
