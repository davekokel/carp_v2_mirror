# carp_app/ui/pages/008_📤_upload_csv_fluors.py
from __future__ import annotations

import io, pathlib, sys
from typing import Optional

import pandas as pd
import streamlit as st
from sqlalchemy.engine import Engine

ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from carp_app.ui.auth_gate import require_auth
from carp_app.ui.email_otp_gate import require_email_otp
from carp_app.ui.lib.app_ctx import get_engine

try:
    from carp_app.ui.auth_gate import require_app_unlock
except Exception:
    def require_app_unlock(): ...

from carp_app.ui.lib.csv_loaders_fluors import (
    load_fluors_from_df,
    normalize_fluor_table,
    build_fluor_rows,
)

# ── Auth / page ──────────────────────────────────────────────────────
sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(page_title="CARP — Upload Fluors", page_icon="📤", layout="wide")
st.title("📤 Upload Fluors")
st.caption(
    "CSV/XLSX columns: **fluor_name (or fluor_nickname), excitation_nm, emission_nm, alt_names, notes**. "
    "Excitation/emission are optional; blanks or 0 are stored as NULL. "
    "alt_names may be separated by ';' ',' '|' or '/'. "
    "Aliases are normalized into the global **join_aliases** table (target_kind='fluor')."
)

_ENGINE: Optional[Engine] = None
def _eng() -> Engine:
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = get_engine()
    return _ENGINE

def _example_csv() -> bytes:
    df = pd.DataFrame(
        [
            {
                "fluor_name": "mStayGold",
                "excitation_nm": 506,
                "emission_nm": 550,
                "alt_names": "mSG; tdmStayGold",
                "notes": "example",
            },
            {
                "fluor_name": "mChilada",
                "excitation_nm": 587,
                "emission_nm": 610,
                "alt_names": "",
                "notes": "",
            },
            {
                "fluor_name": "Halo",
                "excitation_nm": "",
                "emission_nm": "",
                "alt_names": "HaloTag; HT7; HaloTag7",
                "notes": "Self-labeling tag; fluoresces with JF dyes",
            },
        ]
    )
    return df.to_csv(index=False).encode("utf-8")

st.download_button(
    "⬇︎ Example fluors.csv",
    data=_example_csv(),
    file_name="fluors_example.csv",
    mime="text/csv",
    use_container_width=True,
)

# ── Upload file ──────────────────────────────────────────────────────
uploaded = st.file_uploader("Upload fluors file (.csv or .xlsx)", type=["csv", "xlsx"])
if not uploaded:
    st.info("Choose a CSV/XLSX to begin.")
    st.stop()

try:
    raw = io.BytesIO(uploaded.getbuffer())
    if uploaded.name.lower().endswith(".xlsx"):
        df_raw = pd.read_excel(raw, sheet_name=0, dtype=object)
    else:
        try:
            df_raw = pd.read_csv(raw, dtype=object, encoding="utf-8")
        except UnicodeDecodeError:
            raw.seek(0)
            df_raw = pd.read_csv(raw, dtype=object, encoding="latin1")
except Exception as e:
    st.error(f"Failed to read file: {e}")
    st.stop()

try:
    out, soft_warn = normalize_fluor_table(df_raw)
except Exception as e:
    st.error(str(e))
    st.stop()

rows = build_fluor_rows(out)
if not rows:
    st.info("Nothing to insert.")
    st.stop()

# Preview
st.subheader("Preview")
st.dataframe(
    out[["fluor_name", "excitation_nm", "emission_nm", "alt_names", "notes", "fluor_code"]].head(
        30
    ),
    use_container_width=True,
    hide_index=True,
)
st.caption(f"{len(out)} rows")
for w in soft_warn:
    st.info(w)

if not st.button("Process upload", type="primary", use_container_width=True):
    st.stop()

created = 0
updated = 0
with _eng().begin() as cx:
    created, updated, rows, soft_warn2 = load_fluors_from_df(df_raw, cx)

st.success(f"Done. Fluors created: {created}, updated: {updated}")
st.download_button(
    "⬇︎ Uploaded fluors (echo CSV)",
    data=pd.DataFrame(rows).to_csv(index=False).encode("utf-8"),
    file_name="fluors_uploaded.csv",
    mime="text/csv",
    use_container_width=True,
)