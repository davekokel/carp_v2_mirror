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

LEGACY_CSV = ROOT / "seed_kits" / "legacy_wrangling_v3" / "working" / "legacy_imaging_annotations_for_db_v9.csv"


def _as_yyyy_mm_dd(series: pd.Series) -> pd.Series:
    dt = pd.to_datetime(series, errors="coerce")
    out = dt.dt.strftime("%Y-%m-%d")
    out = out.where(out.notna(), pd.NA)
    return out.astype("string")


@st.cache_data(ttl=300, show_spinner=False)
def _load_legacy_csv() -> pd.DataFrame:
    if not LEGACY_CSV.exists():
        return pd.DataFrame()

    d = pd.read_csv(LEGACY_CSV, low_memory=False)
    d.columns = [str(c).strip() for c in d.columns]

    keep = [c for c in [
        "roi_dir",
        "plate_date",
        "mount_id",
        "date_mount",
        "date_born",
        "parent_female_genotype_text",
        "parent_male_genotype_text",
        "treatment_rna_rna_base_code",
        "treatment_plasmid_plasmid_base_code",
    ] if c in d.columns]

    if not keep:
        return pd.DataFrame()

    d = d[keep].copy()

    d = d.rename(
        columns={
            "roi_dir": "legacy_roi_dir",
            "plate_date": "legacy_plate_date",
            "mount_id": "legacy_mount_id",
            "date_mount": "legacy_date_mount",
            "date_born": "legacy_date_born",
            "parent_female_genotype_text": "legacy_parent_female_genotype_text",
            "parent_male_genotype_text": "legacy_parent_male_genotype_text",
            "treatment_rna_rna_base_code": "legacy_treatment_rna_rna_base_code",
            "treatment_plasmid_plasmid_base_code": "legacy_treatment_plasmid_plasmid_base_code",
        }
    )

    for c in ["legacy_date_mount", "legacy_date_born"]:
        if c in d.columns:
            d[c] = _as_yyyy_mm_dd(d[c])

    return d


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
    with _ENGINE.begin() as con:
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
        "experiment_names": exp_names["experiment_name"].astype(str).tolist(),
        "min_date": dates.iloc[0]["min_date"],
        "max_date": dates.iloc[0]["max_date"],
    }


def _load_rois(params: Dict[str, Any]) -> pd.DataFrame:
    have = set(_cols(VIEW_NAME))

    # Only the columns we want on this page
    select_cols = [
        "roi_path",
        "tx_gt_fluororganelle",
        "tx_gt_tg",
        "tx_gt_fluortag",
        "roi_note_anatomy",
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
        # robust: prefer treated_clutch_code if present, else treatment_code, else treatment_text
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
    c1, c2, c3, c4, c5 = st.columns([2, 2, 1, 1, 1])
    q = c1.text_input("Search", value="", placeholder="roi, clutch, treatment, tx_gt, genotype, paths…")
    experiment_names = c2.multiselect("Experiment name", options=choices["experiment_names"])
    limit = c3.selectbox("Limit", options=[200, 500, 1000, 2000, 5000], index=2)
    only_treated = c4.checkbox("Only treated", value=False)
    show_debug = c5.checkbox("Show debug columns", value=False)

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
        "show_debug": show_debug,
    }
)

st.caption(f"{len(df):,} row(s) shown")

st.dataframe(
    df,
    width="stretch",
    hide_index=True,
    column_config={
        "experiment_name": st.column_config.TextColumn("experiment_name", width="large"),
        "roi_code": st.column_config.TextColumn("roi_code", width="medium"),
        "roi_path": st.column_config.TextColumn("roi_path", width="large"),
        "clutch_code": st.column_config.TextColumn("clutch_code", width="small"),
        "treatment_code": st.column_config.TextColumn("treatment_code", width="small"),
        "tx_gt_tg": st.column_config.TextColumn("tx_gt_tg", width="large"),
        "tx_gt_fluortag": st.column_config.TextColumn("tx_gt_fluortag", width="large"),
        "tx_gt_fluororganelle": st.column_config.TextColumn("tx_gt_fluororganelle", width="large"),
        "roi_note_anatomy": st.column_config.TextColumn("roi_note_anatomy", width="medium"),
        "plate_note": st.column_config.TextColumn("plate_note", width="medium"),
        "slot_note": st.column_config.TextColumn("slot_note", width="medium"),
    },
)

csv = df.to_csv(index=False).encode("utf-8")
st.download_button("Download CSV", data=csv, file_name="rois_flat.csv", mime="text/csv")
st.caption(f"{len(df):,} row(s) exported (exactly what you see)")
