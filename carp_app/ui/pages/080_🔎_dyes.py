from __future__ import annotations
import pathlib, sys
from typing import Optional, List, Dict
import pandas as pd
import streamlit as st
from sqlalchemy import text
from sqlalchemy.engine import Engine

# repo root
ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from carp_app.ui.auth_gate import require_auth
from carp_app.ui.email_otp_gate import require_email_otp
try:
    from carp_app.ui.auth_gate import require_app_unlock
except:
    def require_app_unlock(): ...
from carp_app.ui.lib.page_engine import engine

# page config
st.set_page_config(page_title="CARP — Overview: Dyes", page_icon="🎨", layout="wide")
sb, session, user = require_auth()
require_email_otp()
require_app_unlock()
st.title("🎨 Overview: Dyes")


def _eng() -> Engine:
    return engine()


def _norm(s: Optional[str]) -> str:
    return (s or "").strip()


# ───────────────────────────────────────────────────────
# FILTERS
# ───────────────────────────────────────────────────────
with st.form("dye_filters", clear_on_submit=False):
    c1, c2 = st.columns([3, 1])
    with c1:
        q_raw = st.text_input(
            "Search (code / nickname / display_name / notes / linked fluor)",
            "",
        )
    with c2:
        lim = int(st.number_input("Limit", min_value=50, max_value=5000,
                                  value=1000, step=50))
    _ = st.form_submit_button("Apply")

q = _norm(q_raw)
q_param = q or None

# ───────────────────────────────────────────────────────
# QUERY
# ───────────────────────────────────────────────────────
sql = text("""
    SELECT
      d.id::text AS id,
      d.code,
      d.nickname,
      d.display_name,
      d.notes,
      d.created_at,
      f.code AS fluor_code,
      f.display_name AS fluor_display_name,
      f.excitation_nm,
      f.emission_nm
    FROM public.dyes d
    LEFT JOIN public.fluors f ON f.id = d.fluor_id
    WHERE (
         :q IS NULL
      OR  d.code ILIKE :ql
      OR  d.nickname ILIKE :ql
      OR  d.display_name ILIKE :ql
      OR  d.notes ILIKE :ql
      OR  COALESCE(f.display_name,'') ILIKE :ql
    )
    ORDER BY d.display_name, d.code
    LIMIT :lim;
""")

params = {
    "q": q_param,
    "ql": f"%{q}%" if q else None,
    "lim": lim,
}

with _eng().begin() as cx:
    df = pd.read_sql(sql, cx, params=params)

df = df.fillna("")
st.caption(f"{len(df)} dye(s)")

# ───────────────────────────────────────────────────────
# TABLE
# ───────────────────────────────────────────────────────
view = pd.DataFrame(
    {
        "code": df["code"],
        "nickname": df["nickname"],
        "display_name": df["display_name"],
        "notes": df["notes"],
        "excitation_nm": df["excitation_nm"],
        "emission_nm": df["emission_nm"],
        "created_at": df["created_at"],
        "fluor_code": df["fluor_code"],
        "fluor_display_name": df["fluor_display_name"],
        "id": df["id"],
    }
)

view.insert(0, "✓ Select", False)

grid = st.data_editor(
    view,
    use_container_width=True,
    hide_index=True,
    num_rows="fixed",
    column_order=[
        "✓ Select",
        "code",
        "nickname",
        "display_name",
        "notes",
        "excitation_nm",
        "emission_nm",
        "created_at",
    ],
    column_config={
        "✓ Select": st.column_config.CheckboxColumn("✓", default=False),
        "code": st.column_config.TextColumn("code (DYE-…)", disabled=True),
        "nickname": st.column_config.TextColumn("nickname", disabled=True),
        "display_name": st.column_config.TextColumn("display_name", disabled=True),
        "notes": st.column_config.TextColumn("Notes", disabled=True),
        "excitation_nm": st.column_config.NumberColumn("Ex (nm)", disabled=True),
        "emission_nm": st.column_config.NumberColumn("Em (nm)", disabled=True),
        "created_at": st.column_config.DatetimeColumn("Created", disabled=True),
    },
)

# ───────────────────────────────────────────────────────
# DETAILS
# ───────────────────────────────────────────────────────
st.divider()
st.subheader("Dye details")

selected_idxs: List[int] = []
if "✓ Select" in grid.columns:
    selected_idxs = grid.index[grid["✓ Select"] == True].tolist()

if len(selected_idxs) == 1:
    row = grid.loc[selected_idxs[0]]

    linked_fluor = ""
    if row["fluor_display_name"]:
        linked_fluor = row["fluor_display_name"]

    tab1, tab2 = st.tabs(["Overview", "Spectra"])
    with tab1:
        st.write(
            {
                "code": row["code"],
                "nickname": row["nickname"],
                "display_name": row["display_name"],
                "notes": row["notes"],
                "linked_fluor": linked_fluor,
            }
        )
    with tab2:
        st.write(
            {
                "excitation_nm": row["excitation_nm"],
                "emission_nm": row["emission_nm"],
            }
        )
elif len(selected_idxs) > 1:
    st.info("Select exactly one dye to view details.")
else:
    st.caption("Tip: select a row to view details.")

st.download_button(
    "⬇︎ Download dyes (CSV)",
    data=df.to_csv(index=False).encode("utf-8"),
    file_name="dyes_overview_v11.csv",
    type="secondary",
    mime="text/csv",
)