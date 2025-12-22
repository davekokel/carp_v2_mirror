from __future__ import annotations

import sys
import pathlib
from typing import Dict, Any, List

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

from carp_app.ui.lib.app_ctx import get_engine

sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(page_title="CARP — 🔬 ROIs (flat)", page_icon="🔬", layout="wide")
st.title("🔬 ROIs — flat table")

_ENGINE: Engine = get_engine()


@st.cache_data(ttl=60, show_spinner=False)
def _load_filter_choices() -> Dict[str, Any]:
    with _ENGINE.begin() as con:
        exp_names = pd.read_sql(
            text(
                """
                SELECT DISTINCT
                  ps.experiment_name
                FROM public.imaging_roi_annotations ra
                LEFT JOIN public.v11_imaging_plate_slot_overview ps
                  ON ps.slot_id::uuid = ra.slot_id
                WHERE ps.experiment_name IS NOT NULL
                  AND btrim(ps.experiment_name) <> ''
                ORDER BY ps.experiment_name;
                """
            ),
            con,
        )

        dates = pd.read_sql(
            text(
                """
                SELECT
                  min(ps.experiment_date) AS min_date,
                  max(ps.experiment_date) AS max_date
                FROM public.imaging_roi_annotations ra
                LEFT JOIN public.v11_imaging_plate_slot_overview ps
                  ON ps.slot_id::uuid = ra.slot_id;
                """
            ),
            con,
        )

    return {
        "experiment_names": exp_names["experiment_name"].astype(str).tolist() if "experiment_name" in exp_names.columns else [],
        "min_date": dates.iloc[0]["min_date"] if len(dates) else None,
        "max_date": dates.iloc[0]["max_date"] if len(dates) else None,
    }


def _load_rois(params: Dict[str, Any]) -> pd.DataFrame:
    where: List[str] = []
    p: Dict[str, Any] = {}

    q = (params.get("q") or "").strip()
    if q:
        where.append(
            "("
            + " OR ".join(
                [
                    "r.experiment_name ILIKE :q",
                    "r.roi_code ILIKE :q",
                    "r.roi_path ILIKE :q",
                    "r.clutch_code ILIKE :q",
                    "r.treatment_code ILIKE :q",
                    "r.treatment_text ILIKE :q",
                    "r.tx_gt_tg ILIKE :q",
                    "r.tx_gt_fluortag ILIKE :q",
                    "r.tx_gt_fluororganelle ILIKE :q",
                    "r.tg_label ILIKE :q",
                    "r.fluortag_label ILIKE :q",
                    "r.fluororganelle_name ILIKE :q",
                    "r.fluororganelle_basecodes ILIKE :q",
                    "r.plasmids_display ILIKE :q",
                    "r.rnas_display ILIKE :q",
                    "r.dyes_display ILIKE :q",
                    "r.roi_note_anatomy ILIKE :q",
                    "r.slot_orientation ILIKE :q",
                    "r.plate_note ILIKE :q",
                    "r.slot_note ILIKE :q",
                ]
            )
            + ")"
        )
        p["q"] = f"%{q}%"

    exp_names = params.get("experiment_names") or []
    if exp_names:
        where.append("r.experiment_name = ANY(:experiment_names)")
        p["experiment_names"] = exp_names

    date_min = params.get("date_min")
    if date_min is not None:
        where.append("r.experiment_date >= :date_min")
        p["date_min"] = date_min

    date_max = params.get("date_max")
    if date_max is not None:
        where.append("r.experiment_date <= :date_max")
        p["date_max"] = date_max

    if params.get("only_treated"):
        where.append("coalesce(btrim(r.treatment_code),'') <> '' OR coalesce(btrim(r.treated_clutch_code),'') <> ''")

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    limit = int(params.get("limit") or 1000)
    p["limit"] = limit

    sql = f"""
    SELECT
      experiment_date,
      experiment_name,
      plate_note,
      slot_note,
      slot_orientation,
      roi_code,
      roi_index_within_slot,
      roi_path,
      roi_note_anatomy,
      clutch_code,
      treated_clutch_code,
      treatment_code,
      treatment_text,
      tx_gt_tg,
      tx_gt_fluortag,
      tx_gt_fluororganelle,
      rnas_display,
      plasmids_display,
      dyes_display,
      tg_label,
      fluortag_label,
      fluororganelle_name,
      fluororganelle_basecodes
    FROM public.v11_roi_flat_table_display r
    {where_sql}
    ORDER BY
      r.experiment_date DESC NULLS LAST,
      r.experiment_name DESC NULLS LAST,
      r.roi_code,
      r.roi_index_within_slot
    LIMIT :limit;
    """

    with _ENGINE.begin() as con:
        df = pd.read_sql(text(sql), con, params=p)

    return df


choices = _load_filter_choices()

with st.expander("Filters", expanded=True):
    c1, c2, c3, c4 = st.columns([2, 2, 1, 1])
    q = c1.text_input("Search", value="", placeholder="roi, clutch, treatment, labels, paths…")
    experiment_names = c2.multiselect("Experiment name", options=choices["experiment_names"])
    limit = c3.selectbox("Limit", options=[200, 500, 1000, 2000, 5000], index=2)
    only_treated = c4.checkbox("Only treated", value=False)

    d1, d2 = st.columns([1, 1])
    min_d = choices["min_date"]
    max_d = choices["max_date"]
    date_min = d1.date_input("Experiment date from", value=min_d) if min_d is not None else None
    date_max = d2.date_input("Experiment date to", value=max_d) if max_d is not None else None

df = _load_rois(
    {
        "q": q,
        "experiment_names": experiment_names,
        "date_min": date_min,
        "date_max": date_max,
        "limit": limit,
        "only_treated": only_treated,
    }
)

st.caption(f"{len(df):,} row(s) shown")

show_cols = [c for c in [
    "experiment_date",
    "experiment_name",
    "plate_note",
    "slot_note",
    "slot_orientation",
    "roi_code",
    "roi_index_within_slot",
    "roi_path",
    "roi_note_anatomy",
    "clutch_code",
    "treated_clutch_code",
    "treatment_code",
    "treatment_text",
    "tx_gt_tg",
    "tx_gt_fluortag",
    "tx_gt_fluororganelle",
    "rnas_display",
    "plasmids_display",
    "dyes_display",
    "tg_label",
    "fluortag_label",
    "fluororganelle_name",
    "fluororganelle_basecodes",
] if c in df.columns]


def _esc(v) -> str:
    if v is None:
        return ""
    s = str(v)
    return (s.replace("&", "&amp;")
              .replace("<", "&lt;")
              .replace(">", "&gt;"))


_width_px = {
    "experiment_date": 120,
    "experiment_name": 220,
    "plate_note": 220,
    "slot_note": 220,
    "slot_orientation": 110,
    "roi_code": 190,
    "roi_index_within_slot": 80,
    "roi_path": 520,
    "roi_note_anatomy": 220,
    "clutch_code": 160,
    "treated_clutch_code": 180,
    "treatment_code": 180,
    "treatment_text": 420,
    "tx_gt_tg": 360,
    "tx_gt_fluortag": 420,
    "tx_gt_fluororganelle": 420,
    "rnas_display": 220,
    "plasmids_display": 220,
    "dyes_display": 180,
    "tg_label": 240,
    "fluortag_label": 260,
    "fluororganelle_name": 200,
    "fluororganelle_basecodes": 260,
}


colgroup = "".join([
    "<col style='width:" + str(_width_px.get(c, 180)) + "px'>"
    for c in show_cols
])

headers = "".join([
    "<th>" + _esc(c) + "</th>"
    for c in show_cols
])

rows_html = []
for _, r in df[show_cols].iterrows():
    tds = []
    for c in show_cols:
        tds.append("<td><div class='cell'>" + _esc(r[c]) + "</div></td>")
    rows_html.append("<tr>" + "".join(tds) + "</tr>")

css = """
<style>
.carp-roi-wrap {
  width: 100%;
  overflow-x: auto;
  overflow-y: auto;
  max-height: 72vh;
  border: 1px solid #e6e6e6;
  border-radius: 6px;
}
.carp-roi-table {
  border-collapse: collapse;
  width: max-content;
  min-width: 100%;
  table-layout: fixed;
}
.carp-roi-table th, .carp-roi-table td {
  border: 1px solid #e6e6e6;
  padding: 6px 8px;
  vertical-align: top;
}
.carp-roi-table th {
  position: sticky;
  top: 0;
  background: white;
  z-index: 2;
  text-align: left;
  font-weight: 600;
  white-space: nowrap;
}
.carp-roi-table td .cell {
  font-size: 12px;
  line-height: 1.2;
  white-space: normal;
  word-break: break-word;
  overflow-wrap: anywhere;
}
</style>
"""

html = (
    css
    + "<div class='carp-roi-wrap'>"
    + "<table class='carp-roi-table'>"
    + "<colgroup>" + colgroup + "</colgroup>"
    + "<thead><tr>" + headers + "</tr></thead>"
    + "<tbody>" + "".join(rows_html) + "</tbody>"
    + "</table></div>"
)

st.markdown(html, unsafe_allow_html=True)

csv = df.to_csv(index=False).encode("utf-8")
st.download_button("Download CSV", data=csv, file_name="rois_flat.csv", mime="text/csv")
st.caption(f"{len(df):,} row(s) exported (exactly what you see)")
