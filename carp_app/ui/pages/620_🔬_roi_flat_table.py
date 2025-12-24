from __future__ import annotations

import sys
import pathlib
from typing import Dict, Any, List, Optional, Tuple

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


def _split_canonical_tx(v: Any) -> Tuple[str, str]:
    if v is None:
        return ("", "")
    s = str(v).strip()
    if not s or s.lower() in ("nan", "none", "na", "n/a", "<na>"):
        return ("", "")
    if " > " not in s:
        return (s, "")
    a, b = s.split(" > ", 1)
    return (a.strip(), b.strip())

def _format_tx_parts(treat: str, gt: str) -> str:
    a = (treat or "").strip()
    b = (gt or "").strip()
    out = []
    if a:
        out.append(f"treat={a}")
    if b:
        out.append(f"gt={b}")
    return "\n".join(out)



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
                    "r.treated_clutch_codes ILIKE :q",
                    "r.treatment_codes ILIKE :q",
                    "r.tx_gt_tg ILIKE :q",
                    "r.tx_gt_fluortag ILIKE :q",
                    "r.tx_gt_fluororganelle ILIKE :q",
                    "r.plasmids_display ILIKE :q",
                    "r.rnas_display ILIKE :q",
                    "r.dyes_display ILIKE :q",
                    "cast(r.n_tiffs as text) ILIKE :q",
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
        where.append("coalesce(btrim(r.treatment_codes),'') <> '' OR coalesce(btrim(r.treated_clutch_codes),'') <> ''")

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
      roi_id,
      ('roi-' || left(roi_id::text, 8)) AS roi_code,
      r.roi_code AS roi_label,
      roi_index_within_slot,
      roi_path,
      roi_note_anatomy,
      n_tiffs,
      clutch_code,
      treated_clutch_codes AS treated_clutch_code,
      treatment_codes      AS treatment_code,
      tx_gt_tg,
      tx_gt_fluortag,
      tx_gt_fluororganelle,
      plasmids_display,
      rnas_display,
      dyes_display,
      n_channels_total,
      n_channels_kept,
      kept_channels_key
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

    if len(df):
        if "treatment_code" in df.columns:
            df["treatment_code"] = df["treatment_code"].astype(str).fillna("").str.strip()
        if "treated_clutch_code" in df.columns:
            df["treated_clutch_code"] = df["treated_clutch_code"].astype(str).fillna("").str.strip()
        df["has_treatment"] = (
            df.get("treatment_code", "").astype(str).str.strip().ne("")
            & ~df.get("treatment_code", "").astype(str).str.strip().str.lower().isin(["nan","none","na","n/a","<na>"])
        ) | (
            df.get("treated_clutch_code", "").astype(str).str.strip().ne("")
            & ~df.get("treated_clutch_code", "").astype(str).str.strip().str.lower().isin(["nan","none","na","n/a","<na>"])
        )
        for c in ["tx_gt_fluortag_parts", "tx_gt_fluororganelle_parts"]:
            if c in df.columns:
                df[c] = df[c].replace(r"(?s)^treat=\s*\ngt=\s*$", "", regex=True)

    if len(df):
        ft_parts = df["tx_gt_fluortag"].apply(_split_canonical_tx)
        df["tx_gt_fluortag_parts"] = ft_parts.apply(lambda t: _format_tx_parts(t[0], t[1]))

        fo_parts = df["tx_gt_fluororganelle"].apply(_split_canonical_tx)
        df["tx_gt_fluororganelle_parts"] = fo_parts.apply(lambda t: _format_tx_parts(t[0], t[1]))

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

def _n_nonblank(series: pd.Series) -> int:
    if series is None or series.name not in df.columns:
        return 0
    s = series.astype(str).fillna("").map(lambda x: x.strip())
    return int((s != "").sum())

n = len(df)
n_tg = _n_nonblank(df["tx_gt_tg"]) if "tx_gt_tg" in df.columns else 0
n_ft = _n_nonblank(df["tx_gt_fluortag"]) if "tx_gt_fluortag" in df.columns else 0
n_fo = _n_nonblank(df["tx_gt_fluororganelle"]) if "tx_gt_fluororganelle" in df.columns else 0

st.caption(f"{n:,} row(s) shown | tx_gt_tg: {n_tg:,}/{n:,} | tx_gt_fluortag: {n_ft:,}/{n:,} | tx_gt_fluororganelle: {n_fo:,}/{n:,}")

show_cols = [c for c in [
    "experiment_date",
    "experiment_name",
    "roi_code",
    "roi_label",
    "roi_index_within_slot",
    "tx_gt_tg",
    "tx_gt_fluortag",
    "tx_gt_fluororganelle",
    "treated_clutch_code",
    "treatment_code",
    "plasmids_display",
    "rnas_display",
    "dyes_display",
    "n_tiffs",
    "n_channels_kept",
    "n_channels_total",
    "kept_channels_key",
    "roi_note_anatomy",
    "roi_path",
    "clutch_code",
    "plate_note",
    "slot_note",
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
    "slot_orientation": 90,
    "roi_code": 240,
    "roi_index_within_slot": 80,
    "roi_path": 520,
    "clutch_code": 150,
    "treated_clutch_code": 200,
    "treatment_code": 180,
    "tx_gt_tg": 520,
    "tx_gt_fluortag": 520,
    "tx_gt_fluororganelle": 520,
    "tx_gt_fluortag_parts": 360,
    "tx_gt_fluororganelle_parts": 360,
    "plasmids_display": 240,
    "rnas_display": 240,
    "dyes_display": 180,
    "n_tiffs": 90,
    "roi_note_anatomy": 220,
    "plate_note": 220,
    "slot_note": 220,
}

colgroup = "".join([
    "<col style='width:" + str(_width_px.get(c, 180)) + "px'>"
    for c in show_cols
])

headers = "".join([
    "<th>" + _esc(c) + "</th>"
    for c in show_cols
])

def _row_class(r) -> str:
    try:
        v = r.get('has_treatment', False)
        return ' class="is-treated"' if bool(v) else ''
    except Exception:
        return ''

mono_cols = set(["roi_code", "roi_path", "kept_channels_key"])

rows_html = []
for _, r in df.iterrows():
    tds = []
    for c in show_cols:
        cls = "cell mono" if c in mono_cols else "cell"
        tds.append("<td><div class='" + cls + "'>" + _esc(r.get(c, "")) + "</div></td>")
    rows_html.append("<tr" + _row_class(r) + ">" + "".join(tds) + "</tr>")

css = """<style>
.carp-roi-wrap {
  max-height: 70vh;
  overflow: auto;
  border: 1px solid #e6e6e6;
  border-radius: 10px;
}

.carp-roi-table {
  width: 100%;
  border-collapse: separate;
  border-spacing: 0;
  table-layout: fixed;
}

.carp-roi-table th, .carp-roi-table td {
  border-bottom: 1px solid #f0f0f0;
  padding: 6px 8px;
  vertical-align: top;
}

.carp-roi-table th {
  position: sticky;
  top: 0;
  background: #fbfbfb;
  z-index: 3;
  text-align: left;
  font-weight: 650;
  white-space: nowrap;
  border-bottom: 1px solid #e6e6e6;
}

.carp-roi-table tbody tr:nth-child(even) td {
  background: #fcfcfd;
}

.carp-roi-table tbody tr:hover td {
  background: #f6f8ff;
}

.carp-roi-table tbody tr.is-treated td {
  background: #fffef7;
  border-left: 4px solid #f0c36d;
}

.carp-roi-table td .cell {
  font-size: 12px;
  line-height: 1.25;
  white-space: pre-wrap;
  word-break: break-word;
  overflow-wrap: anywhere;
}

.carp-roi-table td .cell.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
  font-size: 11px;
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
