from __future__ import annotations

import os
import pathlib
import sys
from typing import Optional, Dict, Any, List, Tuple

import pandas as pd
import streamlit as st
from sqlalchemy import text
from sqlalchemy.engine import Engine

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
from carp_app.ui.lib.app_ctx import get_engine


# ───────── auth & page ─────────
sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(
    page_title="CARP — Overview Fish",
    page_icon="🐟",
    layout="wide",
)
st.title("🐟 Overview fish")


# ───────── engine ─────────
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


def parse_query(q_raw: str) -> Tuple[Dict[str, str], str]:
    """
    Parse a simple mini-language:

      nickname=casper background=casper mStayGold

    into:

      field_filters = {"nickname": "casper", "background": "casper"}
      free_text     = "mStayGold"

    Any token without '=' goes into the free-text portion.
    """
    field_filters: Dict[str, str] = {}
    free_tokens: List[str] = []

    tokens = q_raw.strip().split()
    for tok in tokens:
        if "=" in tok:
            key, val = tok.split("=", 1)
            key = key.strip().lower()
            val_norm = _norm(val)
            if not val_norm:
                continue
            field_filters[key] = val_norm
        else:
            free_tokens.append(tok)

    free_text = " ".join(free_tokens)
    return field_filters, free_text


# ───────── filters ─────────
with st.form("fish_filters", clear_on_submit=False):
    c1, c2 = st.columns([3, 1])
    with c1:
        q_raw = st.text_input(
            "Search (fish code / line nickname / background / genotype / fluor / tag / organelle)",
            "",
        )
    with c2:
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

field_filters, free_text = parse_query(q_raw or "")

where = ["1=1"]
params: Dict[str, Any] = {"lim": lim}

# Map mini-language field names → columns on v11_fish_instance_star
field_to_column = {
    "nickname": "line_nickname",
    "line_nickname": "line_nickname",
    "name": "line_nickname",
    "background": "genetic_background",
    "bg": "genetic_background",
    "genotype": "genotype_pretty",
    "geno": "genotype_pretty",
    "fluor": "fluor_codes",
    "fluors": "fluor_codes",
    "tag": "tag_codes",
    "tags": "tag_codes",
    "organelle": "organelle_fluors",
    "organelle_fluor": "organelle_fluors",
    "organelle_fluors": "organelle_fluors",
    "code": "fish_code",
    "fish_code": "fish_code",
}

for key, val in field_filters.items():
    col = field_to_column.get(key)
    if not col:
        # unknown field name: treat this as free-text instead
        free_text = (free_text + " " + f"{key}={val}").strip()
        continue
    param_name = f"f_{key}"
    where.append(f"COALESCE({col}, '') ILIKE :{param_name}")
    params[param_name] = f"%{val}%"

if free_text:
    params["ql"] = f"%{free_text}%"
    where.append(
        "("
        "  fish_code                          ILIKE :ql"
        " OR COALESCE(line_nickname,'')      ILIKE :ql"
        " OR COALESCE(genetic_background,'') ILIKE :ql"
        " OR COALESCE(genotype_pretty,'')    ILIKE :ql"
        " OR COALESCE(fluor_codes,'')        ILIKE :ql"
        " OR COALESCE(tag_codes,'')          ILIKE :ql"
        " OR COALESCE(organelle_fluors,'')   ILIKE :ql"
        ")"
    )

where_sql = " AND ".join(where)

# ───────── query v11_fish_instance_star ─────────
sql = text(f"""
    SELECT
      fish_instance_id,
      fish_code,
      line_nickname,
      genetic_background,
      line_building_stage,
      birthday,
      genotype_pretty,
      fluor_codes,
      tag_codes,
      organelle_fluors,
      fish_created_at
    FROM public.v11_fish_instance_star
    WHERE {where_sql}
    ORDER BY fish_created_at DESC NULLS LAST, fish_code
    LIMIT :lim
""")

with _eng().begin() as cx:
    df = pd.read_sql(sql, cx, params=params)

for c in df.select_dtypes(include=["object", "string"]).columns:
    df[c] = df[c].astype("string").fillna("")

st.caption(f"{len(df)} fish")

# ───────── table view ─────────
view = df[
    [
        "fish_code",
        "line_nickname",
        "genetic_background",
        "line_building_stage",
        "birthday",
        "genotype_pretty",
        "fluor_codes",
        "tag_codes",
        "organelle_fluors",
        "fish_created_at",
    ]
].copy()
view.insert(0, "✓ Select", False)

st.data_editor(
    view,
    key="fish_overview_v11",
    hide_index=True,
    use_container_width=True,
    num_rows="fixed",
    column_order=[
        "✓ Select",
        "fish_code",
        "line_nickname",
        "genetic_background",
        "line_building_stage",
        "birthday",
        "genotype_pretty",
        "fluor_codes",
        "tag_codes",
        "organelle_fluors",
        "fish_created_at",
    ],
    column_config={
        "✓ Select":            st.column_config.CheckboxColumn("✓", default=False),
        "fish_code":           st.column_config.TextColumn("Fish code", disabled=True),
        "line_nickname":       st.column_config.TextColumn("Line nickname", disabled=True, width="large"),
        "genetic_background":  st.column_config.TextColumn("Background", disabled=True),
        "line_building_stage": st.column_config.TextColumn("Stage", disabled=True),
        "birthday":            st.column_config.DateColumn("Birthday", disabled=True),
        "genotype_pretty":     st.column_config.TextColumn("Genotype (pretty)", disabled=True, width="large"),
        "fluor_codes":         st.column_config.TextColumn("Fluors", disabled=True),
        "tag_codes":           st.column_config.TextColumn("Tags", disabled=True),
        "organelle_fluors":    st.column_config.TextColumn("Organelle-fluors", disabled=True, width="large"),
        "fish_created_at":     st.column_config.DatetimeColumn("Created at", disabled=True),
    },
)

st.download_button(
    "⬇︎ Download fish overview (CSV)",
    data=df.to_csv(index=False).encode("utf-8"),
    file_name="fish_overview.csv",
    type="secondary",
    mime="text/csv",
)