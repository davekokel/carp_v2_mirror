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
    show_debug = bool(params.get("show_debug"))

    # Primary display fields (the point of this page)
    top_cols = [
        "experiment_date",
        "experiment_name",
        "roi_code",
        "roi_path",
        "clutch_code",
        "treated_clutch_code",
        "treatment_code",
        "treatment_text",

        "tx_gt_tg",
        "tx_gt_fluortag",
        "tx_gt_fluororganelle",

        "genotype_pretty",

        "created_at",
    ]

    tail_cols = [
        "plate_code",
        "slot_index",
        "slot_label",
        "roi_index_within_slot",
        "roi_note_anatomy",
        "plate_note",
        "slot_note",
    ]

    debug_cols = [
        "treatment_pretty_tg",
        "treatment_pretty_fluortag",
        "treatment_pretty_fluororganelle",
        "marker_rollup_display_tg",
        "marker_rollup_display_fluortag",
        "marker_rollup_display_fluororganelle",
        "genotype_basecodes",
    ]

    base = top_cols + tail_cols + (debug_cols if show_debug else [])
    select_cols = [c for c in base if c in have]

    where: List[str] = []
    p: Dict[str, Any] = {}

    q = (params.get("q") or "").strip()
    if q:
        like_cols = [
            "roi_code",
            "roi_path",
            "experiment_name",
            "plate_code",
            "slot_label",
            "clutch_code",
            "treated_clutch_code",
            "treatment_code",
            "treatment_text",
            "tx_gt_tg",
            "tx_gt_fluortag",
            "tx_gt_fluororganelle",
            "genotype_pretty",
        ]
        like_cols = [c for c in like_cols if c in have]
        if like_cols:
            where.append("(" + " or ".join([f"{c} ilike :q" for c in like_cols]) + ")")
            p["q"] = f"%{q}%"

    exp_names = params.get("experiment_names") or []
    if exp_names:
        where.append("experiment_name = any(:experiment_names)")
        p["experiment_names"] = exp_names

    date_min = params.get("date_min")
    if date_min is not None:
        where.append("experiment_date >= :date_min")
        p["date_min"] = date_min

    date_max = params.get("date_max")
    if date_max is not None:
        where.append("experiment_date <= :date_max")
        p["date_max"] = date_max

    if params.get("only_treated"):
        where.append("coalesce(btrim(treatment_code),'') <> ''")

    where_sql = ("where " + " and ".join(where)) if where else ""

    limit = int(params.get("limit") or 1000)
    p["limit"] = limit

    sql = f"""
    select
      {", ".join(select_cols)}
    from public.{VIEW_NAME}
    {where_sql}
    order by experiment_date desc nulls last, plate_code desc nulls last, slot_index, roi_index_within_slot
    limit :limit;
    """

    with _ENGINE.begin() as con:
        df = pd.read_sql(text(sql), con, params=p)

    legacy = _load_legacy_csv()
    if not legacy.empty and "roi_path" in df.columns:
        df = df.merge(
            legacy,
            left_on="roi_path",
            right_on="legacy_roi_dir",
            how="left",
        )

    if getattr(df, "columns", None) is not None and df.columns.duplicated().any():
        df = df.loc[:, ~df.columns.duplicated()].copy()

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
        "experiment_date": st.column_config.DateColumn("experiment_date", width="small"),
        "experiment_name": st.column_config.TextColumn("experiment_name", width="large"),
        "roi_code": st.column_config.TextColumn("roi_code", width="medium"),
        "roi_path": st.column_config.TextColumn("roi_path", width="large"),
        "clutch_code": st.column_config.TextColumn("clutch_code", width="small"),
        "treated_clutch_code": st.column_config.TextColumn("treated_clutch_code", width="small"),
        "treatment_code": st.column_config.TextColumn("treatment_code", width="small"),
        "treatment_text": st.column_config.TextColumn("treatment_text", width="medium"),

        "tx_gt_tg": st.column_config.TextColumn("tx_gt_tg", width="large"),
        "tx_gt_fluortag": st.column_config.TextColumn("tx_gt_fluortag", width="large"),
        "tx_gt_fluororganelle": st.column_config.TextColumn("tx_gt_fluororganelle", width="large"),

        "genotype_pretty": st.column_config.TextColumn("genotype_pretty", width="large"),
        "created_at": st.column_config.DatetimeColumn("created_at", width="medium"),

        "plate_code": st.column_config.TextColumn("plate_code", width="small"),
        "slot_index": st.column_config.NumberColumn("slot_index", width="small"),
        "slot_label": st.column_config.TextColumn("slot_label", width="small"),
        "roi_index_within_slot": st.column_config.NumberColumn("roi_index_within_slot", width="small"),

        "roi_note_anatomy": st.column_config.TextColumn("roi_note_anatomy", width="medium"),
        "plate_note": st.column_config.TextColumn("plate_note", width="medium"),
        "slot_note": st.column_config.TextColumn("slot_note", width="medium"),

        "treatment_pretty_tg": st.column_config.TextColumn("treatment_pretty_tg", width="large"),
        "treatment_pretty_fluortag": st.column_config.TextColumn("treatment_pretty_fluortag", width="large"),
        "treatment_pretty_fluororganelle": st.column_config.TextColumn("treatment_pretty_fluororganelle", width="large"),

        "marker_rollup_display_tg": st.column_config.TextColumn("marker_rollup_display_tg", width="large"),
        "marker_rollup_display_fluortag": st.column_config.TextColumn("marker_rollup_display_fluortag", width="large"),
        "marker_rollup_display_fluororganelle": st.column_config.TextColumn("marker_rollup_display_fluororganelle", width="large"),

        "genotype_basecodes": st.column_config.TextColumn("genotype_basecodes", width="large"),

        "legacy_roi_dir": st.column_config.TextColumn("legacy_roi_dir", width="large"),
        "legacy_plate_date": st.column_config.TextColumn("legacy_plate_date", width="small"),
        "legacy_mount_id": st.column_config.TextColumn("legacy_mount_id", width="small"),
        "legacy_date_mount": st.column_config.TextColumn("legacy_date_mount", width="small"),
        "legacy_date_born": st.column_config.TextColumn("legacy_date_born", width="small"),
        "legacy_parent_female_genotype_text": st.column_config.TextColumn("legacy_parent_female_genotype_text", width="large"),
        "legacy_parent_male_genotype_text": st.column_config.TextColumn("legacy_parent_male_genotype_text", width="large"),
        "legacy_treatment_rna_rna_base_code": st.column_config.TextColumn("legacy_treatment_rna_rna_base_code", width="large"),
        "legacy_treatment_plasmid_plasmid_base_code": st.column_config.TextColumn("legacy_treatment_plasmid_plasmid_base_code", width="large"),
    },
)

csv = df.to_csv(index=False).encode("utf-8")
st.download_button("Download CSV", data=csv, file_name="rois_flat.csv", mime="text/csv")
st.caption(f"{len(df):,} row(s) exported (exactly what you see)")
