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

VIEW_NAME = "v_roi_overview_display_v6"
_ENGINE: Engine = get_engine()


@st.cache_data(ttl=60, show_spinner=False)
def _cols(table_or_view: str) -> List[str]:
    with _ENGINE.begin() as con:
        rows = con.execute(
            text(
                """
                select column_name
                from information_schema.columns
                where table_schema='public' and table_name=:t
                order by ordinal_position
                """
            ),
            {"t": table_or_view},
        ).fetchall()
    return [r[0] for r in rows]


@st.cache_data(ttl=60, show_spinner=False)
def _load_filter_choices() -> Dict[str, Any]:
    have = set(_cols(VIEW_NAME))
    with _ENGINE.begin() as con:
        exp_names = pd.DataFrame({"experiment_name": []})
        if "experiment_name" in have:
            exp_names = pd.read_sql(
                text(
                    f"""
                    select distinct experiment_name
                    from public.{VIEW_NAME}
                    where experiment_name is not null and btrim(experiment_name) <> ''
                    order by experiment_name;
                    """
                ),
                con,
            )

        dates = pd.DataFrame({"min_date": [None], "max_date": [None]})
        if "experiment_date" in have:
            dates = pd.read_sql(
                text(
                    f"""
                    select min(experiment_date) as min_date, max(experiment_date) as max_date
                    from public.{VIEW_NAME};
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
    have = set(_cols(VIEW_NAME))

    select_cols = [
        "roi_path",
        "tx_gt_fluororganelle",
        "tx_gt_tg",
        "tx_gt_fluortag",
        "roi_note_anatomy",
        "slot_orientation",
        "plate_note",
        "slot_note",
        "experiment_name",
        "roi_code",
        "clutch_code",
        "treatment_code",
    ]
    select_cols = [c for c in select_cols if c in have]
    if not select_cols:
        raise SystemExit(f"[STOP] {VIEW_NAME} has none of the expected columns; have={sorted(have)}")

    where: List[str] = []
    p: Dict[str, Any] = {}

    q = (params.get("q") or "").strip()
    if q:
        like_cols = [
            "experiment_name",
            "roi_code",
            "roi_path",
            "clutch_code",
            "treatment_code",
            "tx_gt_tg",
            "tx_gt_fluortag",
            "tx_gt_fluororganelle",
            "roi_note_anatomy",
            "slot_orientation",
            "plate_note",
            "slot_note",
        ]
        like_cols = [c for c in like_cols if c in have]
        if like_cols:
            where.append("(" + " OR ".join([f"{c} ILIKE :q" for c in like_cols]) + ")")
            p["q"] = f"%{q}%"

    exp_names = params.get("experiment_names") or []
    if exp_names and "experiment_name" in have:
        where.append("experiment_name = ANY(:experiment_names)")
        p["experiment_names"] = exp_names

    date_min = params.get("date_min")
    if date_min is not None and "experiment_date" in have:
        where.append("experiment_date >= :date_min")
        p["date_min"] = date_min

    date_max = params.get("date_max")
    if date_max is not None and "experiment_date" in have:
        where.append("experiment_date <= :date_max")
        p["date_max"] = date_max

    if params.get("only_treated"):
        if "treated_clutch_code" in have:
            where.append("coalesce(btrim(treated_clutch_code),'') <> ''")
        elif "treatment_code" in have:
            where.append("coalesce(btrim(treatment_code),'') <> ''")
        elif "treatment_text" in have:
            where.append("coalesce(btrim(treatment_text),'') <> ''")

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    limit = int(params.get("limit") or 1000)
    p["limit"] = limit

    order_parts: List[str] = []
    if "experiment_date" in have:
        order_parts.append("experiment_date DESC NULLS LAST")
    if "experiment_name" in have:
        order_parts.append("experiment_name DESC NULLS LAST")
    if "plate_code" in have:
        order_parts.append("plate_code DESC NULLS LAST")
    if "slot_index" in have:
        order_parts.append("slot_index")
    if "roi_index_within_slot" in have:
        order_parts.append("roi_index_within_slot")
    order_sql = ("ORDER BY " + ", ".join(order_parts)) if order_parts else ""

    sql = f"""
    SELECT
      {", ".join(select_cols)}
    FROM public.{VIEW_NAME}
    {where_sql}
    {order_sql}
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
