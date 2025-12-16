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

view_name = "v_roi_overview_all"
_ENGINE: Engine = get_engine()

@st.cache_data(ttl=30, show_spinner=False)
def _cols(view_name: str) -> List[str]:
    with _ENGINE.begin() as con:
        rows = con.execute(
            text("""
              SELECT column_name
              FROM information_schema.columns
              WHERE table_schema='public' AND table_name=:t
              ORDER BY ordinal_position
            """),
            {"t": view_name},
        ).fetchall()
    return [r[0] for r in rows]

@st.cache_data(ttl=30, show_spinner=False)
def _load_filter_choices() -> Dict[str, Any]:
    with _ENGINE.begin() as con:
        exp_names = pd.read_sql(
            text(f"""
                SELECT DISTINCT experiment_name
                FROM public.{view_name}
                WHERE experiment_name IS NOT NULL AND experiment_name <> ''
                ORDER BY experiment_name;
            """),
            con,
        )
        dates = pd.read_sql(
            text(f"""
                SELECT min(experiment_date) AS min_date, max(experiment_date) AS max_date
                FROM public.{view_name};
            """),
            con,
        )
    return {
        "experiment_names": exp_names["experiment_name"].astype(str).tolist(),
        "min_date": dates.iloc[0]["min_date"],
        "max_date": dates.iloc[0]["max_date"],
    }

@st.cache_data(ttl=30, show_spinner=True)
def _load_rois(params: Dict[str, Any]) -> pd.DataFrame:
    cols = _cols(view_name)
    have = set(cols)

    select_cols = [
        "created_at",
        "experiment_date",
        "experiment_name",
        "plate_code_daily",
        "plate_code_global",
        "slot_label",
        "slot_index",
        "orientation",
        "roi_code",
        "roi_path",
        "clutch_code",
        "treated_clutch_code",
        "treatment_code",
        "treatment_text",
        "genotype_code",
        "genotype_basecodes",
        "genotype_pretty",
        "marker_rollup_tg",
        "marker_rollup_fluortag",
        "marker_rollup_fluororganelle",
        "legacy_date_mount",
        "legacy_birthday",
        "legacy_orientation",
        "legacy_date_imaged",
        "legacy_imaged_locations",
        "legacy_data_location",
        "legacy_roi_dir",
        "legacy_full_roi_path",
        "legacy_zf_female_genotype",
        "legacy_zf_male_genotype",
        "legacy_additional_plasmids_injected",
        "legacy_additional_mrnas_injected",
        "legacy_additional_proteins",
        "legacy_additional_dye_and_chemicals",
        "roi_note_anatomy",
        "plate_note",
        "slot_note",
    ]
    select_cols = [c for c in select_cols if c in have]

    where = []
    p: Dict[str, Any] = {}

    q = (params.get("q") or "").strip()
    if q:
        like_cols = [
            "roi_code",
            "roi_path",
            "experiment_name",
            "clutch_code",
            "treated_clutch_code",
            "treatment_code",
            "treatment_text",
            "marker_rollup_tg",
            "marker_rollup_fluortag",
            "marker_rollup_fluororganelle",
            "legacy_zf_female_genotype",
            "legacy_zf_male_genotype",
            "legacy_data_location",
            "legacy_roi_dir",
            "legacy_full_roi_path",
        ]
        like_cols = [c for c in like_cols if c in have]
        if like_cols:
            where.append("(" + " OR ".join([f"{c} ILIKE :q" for c in like_cols]) + ")")
            p["q"] = f"%{q}%"

    exp_names = params.get("experiment_names") or []
    if exp_names:
        where.append("experiment_name = ANY(:experiment_names)")
        p["experiment_names"] = exp_names

    date_min = params.get("date_min")
    if date_min is not None:
        where.append("experiment_date >= :date_min")
        p["date_min"] = date_min

    date_max = params.get("date_max")
    if date_max is not None:
        where.append("experiment_date <= :date_max")
        p["date_max"] = date_max

    if params.get("require_plate"):
        if "plate_code_daily" in have:
            where.append("plate_code_daily IS NOT NULL")
        if "slot_label" in have:
            where.append("slot_label IS NOT NULL")

    if params.get("only_missing_label"):
        if "marker_rollup_tg" in have:
            where.append("(marker_rollup_tg IS NULL OR btrim(marker_rollup_tg) = '')")

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    limit = int(params.get("limit") or 1000)
    p["limit"] = limit

    sql = f"""
    SELECT
      {", ".join(select_cols)}
    FROM public.{view_name}
    {where_sql}
    ORDER BY created_at DESC
    LIMIT :limit;
    """

    with _ENGINE.begin() as con:
        return pd.read_sql(text(sql), con, params=p)

choices = _load_filter_choices()

with st.expander("Filters", expanded=True):
    c1, c2, c3, c4 = st.columns([2, 2, 1, 1])
    q = c1.text_input("Search", value="", placeholder="roi, clutch, treatment, rollup, parents, paths…")
    experiment_names = c2.multiselect("Experiment name", options=choices["experiment_names"])
    limit = c3.selectbox("Limit", options=[200, 500, 1000, 2000, 5000], index=2)
    require_plate = c4.checkbox("Only rows with plate/slot labels", value=False)

    c5 = st.columns([1])[0]
    only_missing_label = c5.checkbox("Only missing marker_rollup_tg", value=False)

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
        "require_plate": require_plate,
        "only_missing_label": only_missing_label,
    }
)

st.caption(f"{len(df):,} row(s) shown")

st.dataframe(
    df,
    width="stretch",
    hide_index=True,
    column_config={
        "roi_path": st.column_config.TextColumn("roi_path", width="large"),
        "legacy_roi_dir": st.column_config.TextColumn("legacy_roi_dir", width="large"),
        "legacy_full_roi_path": st.column_config.TextColumn("legacy_full_roi_path", width="large"),
        "legacy_data_location": st.column_config.TextColumn("legacy_data_location", width="large"),
        "experiment_name": st.column_config.TextColumn("experiment_name", width="large"),
        "treatment_text": st.column_config.TextColumn("treatment_text", width="large"),
        "marker_rollup_tg": st.column_config.TextColumn("marker_rollup_tg", width="medium"),
        "marker_rollup_fluortag": st.column_config.TextColumn("marker_rollup_fluortag", width="medium"),
        "marker_rollup_fluororganelle": st.column_config.TextColumn("marker_rollup_fluororganelle", width="medium"),
    },
)

csv = df.to_csv(index=False).encode("utf-8")
st.download_button("Download CSV", data=csv, file_name="rois_flat.csv", mime="text/csv")
st.caption(f"{len(df):,} row(s) exported (exactly what you see)")