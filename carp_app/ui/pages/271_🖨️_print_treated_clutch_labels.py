from __future__ import annotations

import sys
import pathlib
from datetime import datetime
from typing import Optional, Dict, Any, List

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
    def require_app_unlock() -> None:
        ...
from carp_app.ui.lib.page_engine import engine as _engine

HAVE_PRINT_HELPER = False
try:
    from carp_app.ui.lib.labels_components import download_button_for_labels
    HAVE_PRINT_HELPER = True
except Exception:
    pass

sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(
    page_title="CARP — 🖨️ Treated clutch labels (v11)",
    page_icon="🖨️",
    layout="wide",
)
st.title("🖨️ Treated clutch labels (v11)")


def eng() -> Engine:
    return _engine()


def _norm(s: str | None) -> Optional[str]:
    s = (s or "").strip()
    return s or None


@st.cache_data(show_spinner=False)
def load_flat_clutch_treated_selected(
    q: Optional[str],
    from_date: Optional[str],
    to_date: Optional[str],
    limit: int,
) -> pd.DataFrame:
    sql = text(
        """
        SELECT
          level,
          clutch_code,
          clutch_date,
          cross_code,
          cross_date,
          tank_pair_code,
          parents,
          treated_clutch_code,
          treatment_code,
          treat_text,
          selection_label,
          genotype_code,
          genotype_basecodes,
          genotype_pretty,
          transgene_label,
          fluor_tag_label,
          organelle_fluor_label,
          marker_basecode_style,
          marker_fluortag_style,
          marker_organelle_style
        FROM public.v11_clutch_flat_overview_with_parents
        WHERE (
               :q IS NULL
            OR clutch_code                         ILIKE :ql
            OR COALESCE(treated_clutch_code,'')   ILIKE :ql
            OR COALESCE(treatment_code,'')        ILIKE :ql
            OR COALESCE(treat_text,'')            ILIKE :ql
            OR COALESCE(selection_label,'')       ILIKE :ql
            OR COALESCE(genotype_pretty,'')       ILIKE :ql
            OR COALESCE(genotype_basecodes,'')    ILIKE :ql
            OR COALESCE(parents,'')               ILIKE :ql
            OR COALESCE(marker_basecode_style,'') ILIKE :ql
            OR COALESCE(marker_fluortag_style,'') ILIKE :ql
            OR COALESCE(marker_organelle_style,'') ILIKE :ql
        )
        AND (:from_d IS NULL OR clutch_date >= :from_d)
        AND (:to_d   IS NULL OR clutch_date <= :to_d)
        ORDER BY clutch_date DESC NULLS LAST,
                 clutch_code,
                 level,
                 treated_clutch_code NULLS FIRST,
                 selection_label NULLS FIRST
        LIMIT :lim;
        """
    )
    params = {
        "q": q,
        "ql": f"%{q}%" if q else None,
        "from_d": from_date,
        "to_d": to_date,
        "lim": int(limit),
    }
    with eng().begin() as cx:
        df = pd.read_sql(sql, cx, params=params)
    return df.fillna("")


with st.form("treated_clutch_label_filters", clear_on_submit=False):
    c1, c2, c3, c4 = st.columns([3, 1.5, 1.5, 1])
    with c1:
        q_raw = st.text_input(
            "Search (clutch / treated clutch / treatment / selection / parents / markers)",
            "",
        )
    with c2:
        from_raw = st.text_input("From clutch_date (YYYY-MM-DD)", "")
    with c3:
        to_raw = st.text_input("To clutch_date (YYYY-MM-DD)", "")
    with c4:
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

q = _norm(q_raw)
from_d: Optional[str] = None
to_d: Optional[str] = None

if from_raw:
    try:
        datetime.strptime(from_raw, "%Y-%m-%d")
        from_d = from_raw
    except ValueError:
        st.warning("From date must be YYYY-MM-DD if provided.")
if to_raw:
    try:
        datetime.strptime(to_raw, "%Y-%m-%d")
        to_d = to_raw
    except ValueError:
        st.warning("To date must be YYYY-MM-DD if provided.")

flat_df = load_flat_clutch_treated_selected(q, from_d, to_d, lim)

if flat_df.empty:
    st.info("No clutches / treated clutches / selections match the current filters.")
    st.stop()

st.caption(f"{len(flat_df)} flat row(s) (clutch × treated_clutch × selection)")

df = flat_df.copy()
df["is_treated"] = df["treated_clutch_code"] != ""
df["selected"] = False

view_cols = [
    "selected",
    "level",
    "clutch_code",
    "clutch_date",
    "cross_code",
    "cross_date",
    "tank_pair_code",
    "parents",
    "marker_basecode_style",
    "marker_fluortag_style",
    "marker_organelle_style",
    "genotype_code",
    "treatment_code",
    "treated_clutch_code",
    "treat_text",
    "selection_label",
    "genotype_basecodes",
    "genotype_pretty",
]
view_cols = [c for c in view_cols if c in df.columns]

flat_view = df[view_cols].copy()

st.subheader("Flat overview (check rows to print labels)")

edited = st.data_editor(
    flat_view,
    key="flat_clutches_treatments_selections_for_labels",
    hide_index=True,
    use_container_width=True,
    num_rows="fixed",
    column_config={
        "selected": st.column_config.CheckboxColumn(
            "Print", help="Check to include this treated clutch row in label output"
        ),
        "level": st.column_config.TextColumn("Level", disabled=True),
        "clutch_code": st.column_config.TextColumn("Clutch", disabled=True),
        "clutch_date": st.column_config.DateColumn("Clutch date", disabled=True),
        "cross_code": st.column_config.TextColumn("Cross code", disabled=True),
        "cross_date": st.column_config.DateColumn("Cross date", disabled=True),
        "tank_pair_code": st.column_config.TextColumn("Tank pair", disabled=True),
        "parents": st.column_config.TextColumn(
            "Parents", disabled=True, width="large"
        ),
        "marker_basecode_style": st.column_config.TextColumn(
            "Markers — basecode (treat_basecodes > genotype_basecodes)",
            disabled=True,
            width="large",
        ),
        "marker_fluortag_style": st.column_config.TextColumn(
            "Markers — fluor::tag(tag_pos) (treat > genotype)",
            disabled=True,
            width="large",
        ),
        "marker_organelle_style": st.column_config.TextColumn(
            "Markers — organelle–fluor (treat > genotype)",
            disabled=True,
            width="large",
        ),
        "genotype_code": st.column_config.TextColumn(
            "Genotype code", disabled=True
        ),
        "treatment_code": st.column_config.TextColumn(
            "Treatment code", disabled=True
        ),
        "treated_clutch_code": st.column_config.TextColumn(
            "Treated clutch code", disabled=True
        ),
        "treat_text": st.column_config.TextColumn(
            "Treatment text", disabled=True, width="large"
        ),
        "selection_label": st.column_config.TextColumn(
            "Selection label", disabled=True, width="large"
        ),
        "genotype_basecodes": st.column_config.TextColumn(
            "Genotype basecodes", disabled=True, width="large"
        ),
        "genotype_pretty": st.column_config.TextColumn(
            "Genotype pretty", disabled=True, width="large"
        ),
    },
)

selected_mask = (edited["selected"] == True) & (edited["treated_clutch_code"] != "")
df_sel = edited[selected_mask].copy()

st.caption(f"{len(df_sel)} flat row(s) selected for labels.")

if df_sel.empty:
    st.warning("Check at least one treated clutch row to print labels.")
    st.stop()

st.subheader("Label preview")

def make_petri_row(row: pd.Series) -> Dict[str, Any]:
    treated = row.get("treated_clutch_code", "")
    clutch = row.get("clutch_code", "")
    treat_code = row.get("treatment_code", "")
    treat_text = row.get("treat_text", "")
    geno = row.get("marker_basecode_style", "") or row.get("genotype_pretty", "")
    date_str = str(row.get("clutch_date") or "")

    tx_codes = treat_code or ""
    tx_fluors = row.get("marker_organelle_style", "") or row.get("marker_fluortag_style", "")

    return {
        "clutch_instance_code": treated or clutch,
        "clutch_name": treat_text,
        "mom_code": "",
        "dad_code": "",
        "clutch_genotype": geno,
        "date_birth": date_str,
        "tx_codes": tx_codes,
        "tx_fluors": tx_fluors,
    }

petri_rows: List[Dict[str, Any]] = [make_petri_row(r) for _, r in df_sel.iterrows()]
df_labels = pd.DataFrame(petri_rows)

preview_rows = []
for r in petri_rows:
    line1 = r["clutch_instance_code"]
    line2 = r["clutch_genotype"]
    line3 = f"{r['date_birth']} · {r['tx_codes']}" if r["tx_codes"] else r["date_birth"]
    fluors = r["tx_fluors"]
    preview_rows.append(
        {
            "label_line_1": line1,
            "label_line_2": line2,
            "label_line_3": line3,
            "label_fluors": fluors,
        }
    )

df_preview = pd.DataFrame(preview_rows)
st.dataframe(df_preview, use_container_width=True, hide_index=True)

st.subheader("Download / print treated clutch labels")

if HAVE_PRINT_HELPER:
    download_button_for_labels(
        rows=petri_rows,
        builder="petri",
        file_prefix="treated_clutch_labels_v11",
        button_text="🖨️ Print / Download TREATED CLUTCH labels (ALL selected)",
    )
else:
    st.info("Label PDF helper not available; showing CSV payload only.")
    csv_labels = df_labels.to_csv(index=False).encode("utf-8")
    st.download_button(
        "⬇︎ Download treated clutch labels (CSV)",
        data=csv_labels,
        file_name="treated_clutch_labels.csv",
        type="primary",
        mime="text/csv",
    )
