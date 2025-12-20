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

VIEW_NAME = "v_roi_overview_rollups"
_ENGINE: Engine = get_engine()

LEGACY_CSV = ROOT / "seed_kits" / "legacy_wrangling_v3" / "working" / "legacy_imaging_annotations_for_db_v9.csv"


def _nonempty(x) -> bool:
    if x is None:
        return False
    s = str(x).strip().lower()
    return s not in ("", "nan", "none", "na", "n/a", "<na>")


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

    keep = [c for c in [
        "roi_dir",
        "Data location",
        "date_mount",
        "zf_female_genotype_from_enrich",
        "zf_male_genotype_from_enrich",
        "additional plasmids injected",
        "additional mRNAs injected",
        "additonal proteins injected",
        "additonal dye and chemicals",
        "Date born",
        "Mounting Orientation",
        "Date imaged",
        "Imaged Locations",
    ] if c in d.columns]

    d = d[keep].copy()

    d = d.rename(columns={
        "roi_dir": "legacy_roi_dir",
        "Data location": "legacy_data_location",
        "date_mount": "legacy_date_mount",
        "zf_female_genotype_from_enrich": "legacy_zf_female_genotype",
        "zf_male_genotype_from_enrich": "legacy_zf_male_genotype",
        "additional plasmids injected": "legacy_additional_plasmids_injected",
        "additional mRNAs injected": "legacy_additional_mrnas_injected",
        "additonal proteins injected": "legacy_additional_proteins",
        "additonal dye and chemicals": "legacy_additional_dye_and_chemicals",
        "Date born": "legacy_birthday",
        "Mounting Orientation": "legacy_orientation",
        "Date imaged": "legacy_date_imaged",
        "Imaged Locations": "legacy_imaged_locations",
    })

    for c in ["legacy_date_mount", "legacy_date_imaged", "legacy_birthday"]:
        if c in d.columns:
            d[c] = _as_yyyy_mm_dd(d[c])

    return d


@st.cache_data(ttl=30, show_spinner=False)
def _cols(table_or_view: str) -> List[str]:
    with _ENGINE.begin() as con:
        rows = con.execute(
            text("""
              SELECT column_name
              FROM information_schema.columns
              WHERE table_schema='public' AND table_name=:t
              ORDER BY ordinal_position
            """),
            {"t": table_or_view},
        ).fetchall()
    return [r[0] for r in rows]


@st.cache_data(ttl=30, show_spinner=False)
def _load_filter_choices() -> Dict[str, Any]:
    with _ENGINE.begin() as con:
        exp_names = pd.read_sql(
            text(f"""
                SELECT DISTINCT experiment_name
                FROM public.{VIEW_NAME}
                WHERE experiment_name IS NOT NULL AND btrim(experiment_name) <> ''
                ORDER BY experiment_name;
            """),
            con,
        )
        dates = pd.read_sql(
            text(f"""
                SELECT min(experiment_date) AS min_date, max(experiment_date) AS max_date
                FROM public.{VIEW_NAME};
            """),
            con,
        )
    return {
        "experiment_names": exp_names["experiment_name"].astype(str).tolist(),
        "min_date": dates.iloc[0]["min_date"],
        "max_date": dates.iloc[0]["max_date"],
    }


def _load_rois(params: Dict[str, Any]) -> pd.DataFrame:
    cols = _cols(VIEW_NAME)
    have = set(cols)

    select_cols = [
        "experiment_date",
        "experiment_name",

        "plate_code",
        "slot_index",
        "slot_label",
        "roi_index_within_slot",
        "roi_code",
        "roi_path",

        "clutch_code",
        "treated_clutch_code",
        "treatment_code",
        "treatment_text",

        "genotype_code",
        "genotype_basecodes",
        "genotype_pretty",

        "genotype_tg_style",
        "genotype_fluortag_style",
        "genotype_fluororganelle_style",

        "marker_rollup_tg",
        "marker_rollup_fluortag",
        "marker_rollup_fluororganelle",

        "label_tg_style",
        "label_fluortag_style",
        "label_fluororganelle_style",

        "roi_note_anatomy",
        "plate_note",
        "slot_note",
        "created_at",
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
            "plate_code",
            "slot_label",
            "clutch_code",
            "treated_clutch_code",
            "treatment_code",
            "treatment_text",
            "genotype_code",
            "genotype_basecodes",
            "genotype_pretty",
            "genotype_tg_style",
            "genotype_fluortag_style",
            "genotype_fluororganelle_style",
            "marker_rollup_tg",
            "marker_rollup_fluortag",
            "marker_rollup_fluororganelle",
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

    if params.get("only_treated"):
        where.append("coalesce(treated_clutch_code,'') <> ''")

    if params.get("only_with_genotype"):
        where.append("coalesce(genotype_code,'') <> ''")

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    limit = int(params.get("limit") or 1000)
    p["limit"] = limit

    sql = f"""
    SELECT
      {", ".join(select_cols)}
    FROM public.{VIEW_NAME}
    {where_sql}
    ORDER BY experiment_date DESC NULLS LAST, plate_code DESC NULLS LAST, slot_index, roi_index_within_slot
    LIMIT :limit;
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

    if "legacy_data_location_filled" not in df.columns:
        if "legacy_data_location" in df.columns and "legacy_roi_dir" in df.columns:
            df["legacy_data_location_filled"] = df.apply(
                lambda r: r["legacy_data_location"] if _nonempty(r.get("legacy_data_location")) else r.get("legacy_roi_dir"),
                axis=1,
            )
        else:
            df["legacy_data_location_filled"] = pd.NA

    return df


choices = _load_filter_choices()

with st.expander("Filters", expanded=True):
    c1, c2, c3, c4, c5 = st.columns([2, 2, 1, 1, 1])
    q = c1.text_input("Search", value="", placeholder="roi, clutch, treatment, rollups, genotype, paths…")
    experiment_names = c2.multiselect("Experiment name", options=choices["experiment_names"])
    limit = c3.selectbox("Limit", options=[200, 500, 1000, 2000, 5000], index=2)
    only_treated = c4.checkbox("Only treated", value=False)
    only_with_genotype = c5.checkbox("Only with genotype", value=False)

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
        "only_with_genotype": only_with_genotype,
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
        "plate_code": st.column_config.TextColumn("plate_code", width="small"),
        "slot_index": st.column_config.NumberColumn("slot_index", width="small"),
        "slot_label": st.column_config.TextColumn("slot_label", width="small"),
        "roi_index_within_slot": st.column_config.NumberColumn("roi_index_within_slot", width="small"),
        "roi_code": st.column_config.TextColumn("roi_code", width="medium"),
        "roi_path": st.column_config.TextColumn("roi_path", width="large"),

        "clutch_code": st.column_config.TextColumn("clutch_code", width="small"),
        "treated_clutch_code": st.column_config.TextColumn("treated_clutch_code", width="small"),
        "treatment_code": st.column_config.TextColumn("treatment_code", width="small"),
        "treatment_text": st.column_config.TextColumn("treatment_text", width="large"),

        "genotype_code": st.column_config.TextColumn("genotype_code", width="small"),
        "genotype_basecodes": st.column_config.TextColumn("genotype_basecodes", width="large"),
        "genotype_tg_style": st.column_config.TextColumn("genotype_tg_style", width="large"),
        "genotype_fluortag_style": st.column_config.TextColumn("genotype_fluortag_style", width="large"),
        "genotype_fluororganelle_style": st.column_config.TextColumn("genotype_fluororganelle_style", width="large"),

        "marker_rollup_tg": st.column_config.TextColumn("marker_rollup_tg", width="large"),
        "marker_rollup_fluortag": st.column_config.TextColumn("marker_rollup_fluortag", width="large"),
        "marker_rollup_fluororganelle": st.column_config.TextColumn("marker_rollup_fluororganelle", width="large"),

        "legacy_roi_dir": st.column_config.TextColumn("legacy_roi_dir", width="large"),
        "legacy_data_location_filled": st.column_config.TextColumn("legacy_data_location_filled", width="large"),
        "legacy_data_location": st.column_config.TextColumn("legacy_data_location", width="large"),
    },
)

csv = df.to_csv(index=False).encode("utf-8")
st.download_button("Download CSV", data=csv, file_name="rois_flat.csv", mime="text/csv")
st.caption(f"{len(df):,} row(s) exported (exactly what you see)")
