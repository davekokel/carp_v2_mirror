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
    WITH base AS (
      SELECT
        ps.experiment_date,
        ps.experiment_name,
        ps.plate_note,
        ps.slot_note,
        ps.slot_orientation,
        ra.roi_code,
        ra.roi_index_within_slot,
        ra.roi_note_anatomy,
        ra.roi_path,
        ps.clutch_code,
        tg.treated_clutch_code,
        ps.treat_code AS treatment_code,
        ps.treat_text AS treatment_text,
        NULLIF(btrim(tg.treatment_label_tg_style), '') AS marker_rollup_display_tg,
        NULLIF(btrim(tg.treatment_label_fluortag_style), '') AS marker_rollup_display_fluortag,
        NULLIF(btrim(tg.treatment_label_fluororganelle_style), '') AS marker_rollup_display_fluororganelle
      FROM public.imaging_roi_annotations ra
      LEFT JOIN public.v11_imaging_plate_slot_overview ps
        ON ps.slot_id::uuid = ra.slot_id
      LEFT JOIN public.v11_treated_clutch_genotype_star_labels tg
        ON tg.genotype_code = ps.genotype_code
    ),
    rows AS (
      SELECT
        roi_path,
        roi_note_anatomy,
        slot_orientation,
        plate_note,
        slot_note,
        experiment_name,
        experiment_date,
        roi_code,
        roi_index_within_slot,
        clutch_code,
        treated_clutch_code,
        treatment_code,
        treatment_text,

        CASE
          WHEN COALESCE(btrim(treatment_text), '') <> '' THEN
            CASE
              WHEN COALESCE(btrim(marker_rollup_display_tg), '') <> ''
                THEN (treatment_text || ' > ' || marker_rollup_display_tg)
              ELSE NULL
            END
          ELSE NULLIF(btrim(marker_rollup_display_tg), '')
        END AS tx_gt_tg,

        CASE
          WHEN COALESCE(btrim(treatment_text), '') <> '' THEN
            CASE
              WHEN COALESCE(btrim(marker_rollup_display_fluortag), '') <> ''
                THEN (treatment_text || ' > ' || marker_rollup_display_fluortag)
              ELSE NULL
            END
          ELSE NULLIF(btrim(marker_rollup_display_fluortag), '')
        END AS tx_gt_fluortag,

        CASE
          WHEN COALESCE(btrim(treatment_text), '') <> '' THEN
            CASE
              WHEN COALESCE(btrim(marker_rollup_display_fluororganelle), '') <> ''
                THEN (treatment_text || ' > ' || marker_rollup_display_fluororganelle)
              ELSE NULL
            END
          ELSE NULLIF(btrim(marker_rollup_display_fluororganelle), '')
        END AS tx_gt_fluororganelle

      FROM base
    )
    SELECT
      roi_path,
      tx_gt_fluororganelle,
      tx_gt_tg,
      tx_gt_fluortag,
      roi_note_anatomy,
      slot_orientation,
      plate_note,
      slot_note,
      experiment_name,
      roi_code,
      clutch_code,
      treatment_code
    FROM rows r
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
    q = c1.text_input("Search", value="", placeholder="roi, clutch, treatment, tx_gt, paths…")
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

st.dataframe(
    df,
    width="stretch",
    hide_index=True,
    column_config={
        "roi_path": st.column_config.TextColumn("roi_path", width="large"),
        "tx_gt_fluororganelle": st.column_config.TextColumn("tx_gt_fluororganelle", width="large"),
        "tx_gt_tg": st.column_config.TextColumn("tx_gt_tg", width="large"),
        "tx_gt_fluortag": st.column_config.TextColumn("tx_gt_fluortag", width="large"),
        "roi_note_anatomy": st.column_config.TextColumn("roi_note_anatomy", width="medium"),
        "slot_orientation": st.column_config.TextColumn("slot_orientation", width="small"),
        "plate_note": st.column_config.TextColumn("plate_note", width="medium"),
        "slot_note": st.column_config.TextColumn("slot_note", width="medium"),
        "experiment_name": st.column_config.TextColumn("experiment_name", width="large"),
        "roi_code": st.column_config.TextColumn("roi_code", width="medium"),
        "clutch_code": st.column_config.TextColumn("clutch_code", width="small"),
        "treatment_code": st.column_config.TextColumn("treatment_code", width="small"),
    },
)

csv = df.to_csv(index=False).encode("utf-8")
st.download_button("Download CSV", data=csv, file_name="rois_flat.csv", mime="text/csv")
st.caption(f"{len(df):,} row(s) exported (exactly what you see)")
