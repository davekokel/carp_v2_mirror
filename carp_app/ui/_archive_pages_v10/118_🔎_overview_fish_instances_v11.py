from __future__ import annotations

import os
import pathlib
import sys
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
    def require_app_unlock(): ...

from carp_app.ui.lib.app_ctx import get_engine

# ───────── auth & page ─────────
sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(
    page_title="CARP — v11 Fish instances overview",
    page_icon="🔎",
    layout="wide",
)
st.title("🔎 v11 Fish instances overview")

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
with st.form("fish_instance_filters", clear_on_submit=False):
    c1, c2, c3 = st.columns([3, 1.2, 0.8])
    with c1:
        q_raw = st.text_input(
            "Search (FSH / LINE / group / nickname / background / genotype)",
            "",
        )
    with c2:
        bg_raw = st.text_input("Background contains (optional)", "")
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
bg_like = _norm(bg_raw)

# ───────── query v11_fish_instance_star ─────────
where = ["1=1"]
params: Dict[str, Any] = {"lim": lim}

if q:
    params["ql"] = f"%{q}%"
    where.append(
        "("
        "  fis.fish_code            ILIKE :ql"
        " OR fis.line_instance_code ILIKE :ql"
        " OR fis.line_code          ILIKE :ql"
        " OR fis.group_code         ILIKE :ql"
        " OR fis.line_nickname      ILIKE :ql"
        " OR fis.genetic_background ILIKE :ql"
        " OR fis.genotype_pretty    ILIKE :ql"
        ")"
    )

if bg_like:
    params["bg_like"] = f"%{bg_like}%"
    where.append("fis.genetic_background ILIKE :bg_like")

where_sql = " AND ".join(where)

sql = text(f"""
    SELECT
      fis.fish_instance_id,
      fis.fish_code,
      fis.line_instance_code,
      fis.line_code,
      fis.group_code,
      fis.line_nickname,
      fis.genetic_background,
      fis.line_building_stage,
      fis.birthday,
      fis.genotype_pretty,
      fis.fluor_codes,
      fis.tag_codes,
      fis.organelle_fluors,
      fis.tank_code,
      fis.tank_status,
      fis.tank_created_at
    FROM public.v11_fish_instance_star fis
    WHERE {where_sql}
    ORDER BY fis.fish_code, fis.birthday NULLS LAST
    LIMIT :lim;
""")

try:
    with _eng().begin() as cx:
        df = pd.read_sql(sql, cx, params=params)
except Exception as e:
    st.error("Error querying v11_fish_instance_star.")
    st.exception(e)
    st.stop()

for c in df.select_dtypes(include=["object", "string"]).columns:
    df[c] = df[c].astype("string").fillna("")

st.caption(f"{len(df)} fish instance(s)")

# ───────── table ─────────
if df.empty:
    st.info("No fish instances match the current filters.")
else:
    view = df.copy()
    view.insert(0, "✓ Select", False)

    st.data_editor(
        view,
        key="v11_fish_instances_overview",
        hide_index=True,
        use_container_width=True,
        num_rows="fixed",
        column_order=[
            "✓ Select",
            "fish_code",
            "line_instance_code",
            "line_code",
            "group_code",
            "line_nickname",
            "genetic_background",
            "line_building_stage",
            "birthday",
            "genotype_pretty",
            "fluor_codes",
            "tag_codes",
            "organelle_fluors",
            "tank_code",
            "tank_status",
            "tank_created_at",
        ],
        column_config={
            "✓ Select":            st.column_config.CheckboxColumn("✓", default=False),
            "fish_code":           st.column_config.TextColumn("FSH code", disabled=True),
            "line_instance_code":  st.column_config.TextColumn("LINE instance", disabled=True),
            "line_code":           st.column_config.TextColumn("LINE code", disabled=True),
            "group_code":          st.column_config.TextColumn("Group", disabled=True),
            "line_nickname":       st.column_config.TextColumn("Line nickname", disabled=True),
            "genetic_background":  st.column_config.TextColumn("Background", disabled=True),
            "line_building_stage": st.column_config.TextColumn("Stage", disabled=True),
            "birthday":            st.column_config.DateColumn("Birthday", disabled=True),
            "genotype_pretty":     st.column_config.TextColumn("Genotype", disabled=True),
            "fluor_codes":         st.column_config.TextColumn("Fluor codes", disabled=True),
            "tag_codes":           st.column_config.TextColumn("Tag codes", disabled=True),
            "organelle_fluors":    st.column_config.TextColumn("Organelle-fluor", disabled=True),
            "tank_code":           st.column_config.TextColumn("Tank code", disabled=True),
            "tank_status":         st.column_config.TextColumn("Tank status", disabled=True),
            "tank_created_at":     st.column_config.DatetimeColumn("Tank created", disabled=True),
        },
    )

    st.download_button(
        "⬇︎ Download v11 fish instances (CSV)",
        data=df.to_csv(index=False).encode("utf-8"),
        file_name="v11_fish_instances_overview.csv",
        type="secondary",
        mime="text/csv",
    )