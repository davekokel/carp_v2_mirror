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


@st.cache_data(ttl=30, show_spinner=True)
def _load_rois(params: Dict[str, Any]) -> pd.DataFrame:
    cols = _cols(VIEW_NAME)
    have = set(cols)

    select_cols = [
        "experiment_name",
        "experiment_date",
        "roi_path",
        "marker_rollup_tg",
        "marker_rollup_fluortag",
        "marker_rollup_fluororganelle",
        "plate_code",
        "slot_label",
        "slot_index",
        "orientation",
        "roi_code",
        "roi_note_anatomy",
        "created_at",
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
        "label_tg_style",
        "label_fluortag_style",
        "label_fluororganelle_style",
        "plate_note",
        "slot_note",
    ]
    select_cols = [c for c in select_cols if c in have]
    if "roi_path" not in select_cols:
        select_cols = ["roi_path"] + select_cols

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
            "label_tg_style",
            "label_fluortag_style",
            "label_fluororganelle_style",
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
        if "plate_code" in have:
            where.append("plate_code IS NOT NULL")
        if "slot_label" in have:
            where.append("slot_label IS NOT NULL")

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    limit = int(params.get("limit") or 1000)
    p["limit"] = limit

    sql = f"""
    SELECT
      {", ".join(select_cols)}
    FROM public.{VIEW_NAME}
    {where_sql}
    ORDER BY created_at DESC
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

    if "modern_date_mount" not in df.columns:
        df["modern_date_mount"] = df["legacy_date_mount"] if "legacy_date_mount" in df.columns else pd.NA
    if "modern_birthday" not in df.columns:
        df["modern_birthday"] = df["legacy_birthday"] if "legacy_birthday" in df.columns else pd.NA

    for c in ["modern_date_mount", "modern_birthday"]:
        if c in df.columns:
            df[c] = _as_yyyy_mm_dd(df[c])

    group_key = None
    if "treated_clutch_code" in df.columns and df["treated_clutch_code"].map(_nonempty).sum() > 0:
        group_key = "treated_clutch_code"
    elif "clutch_code" in df.columns:
        group_key = "clutch_code"

    if group_key:
        if "n_slots" not in df.columns:
            if "slot_label" in df.columns:
                df["n_slots"] = df.groupby(group_key)["slot_label"].transform("nunique")
            else:
                df["n_slots"] = pd.NA

        if "n_rois" not in df.columns:
            if "roi_code" in df.columns:
                df["n_rois"] = df.groupby(group_key)["roi_code"].transform("nunique")
            else:
                df["n_rois"] = pd.NA
    else:
        df["n_slots"] = pd.NA
        df["n_rois"] = pd.NA

    front_order = [
        "experiment_name",
        "experiment_date",
        "roi_path",
        "marker_rollup_tg",
        "marker_rollup_fluortag",
        "marker_rollup_fluororganelle",
        "modern_date_mount",
        "modern_birthday",
        "n_slots",
        "n_rois",
    ]

    legacy_order = [
        "legacy_data_location_filled",
        "legacy_data_location",
        "legacy_date_mount",
        "legacy_zf_female_genotype",
        "legacy_zf_male_genotype",
        "legacy_additional_plasmids_injected",
        "legacy_additional_mrnas_injected",
        "legacy_additional_proteins",
        "legacy_additional_dye_and_chemicals",
        "legacy_birthday",
        "legacy_orientation",
        "legacy_date_imaged",
        "legacy_imaged_locations",
        "legacy_roi_dir",
    ]

    front = [c for c in (front_order + legacy_order) if c in df.columns]
    rest = [c for c in df.columns if c not in front]
    df = df[front + rest]

    return df


choices = _load_filter_choices()

with st.expander("Filters", expanded=True):
    c1, c2, c3, c4 = st.columns([2, 2, 1, 1])
    q = c1.text_input("Search", value="", placeholder="roi, clutch, treatment, rollup, parents, paths…")
    experiment_names = c2.multiselect("Experiment name", options=choices["experiment_names"])
    limit = c3.selectbox("Limit", options=[200, 500, 1000, 2000, 5000], index=2)
    require_plate = c4.checkbox("Only rows with plate/slot labels", value=False)

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
    }
)

st.caption(f"{len(df):,} row(s) shown")

st.dataframe(
    df,
    width="stretch",
    hide_index=True,
    column_config={
        "experiment_name": st.column_config.TextColumn("experiment_name", width="large"),
        "roi_path": st.column_config.TextColumn("roi_path", width="large"),
        "legacy_roi_dir": st.column_config.TextColumn("legacy_roi_dir", width="large"),
        "legacy_data_location_filled": st.column_config.TextColumn("legacy_data_location_filled", width="large"),
        "legacy_data_location": st.column_config.TextColumn("legacy_data_location", width="large"),
        "treatment_text": st.column_config.TextColumn("treatment_text", width="large"),
        "marker_rollup_tg": st.column_config.TextColumn("marker_rollup_tg", width="large"),
        "marker_rollup_fluortag": st.column_config.TextColumn("marker_rollup_fluortag", width="large"),
        "marker_rollup_fluororganelle": st.column_config.TextColumn("marker_rollup_fluororganelle", width="large"),
        "label_tg_style": st.column_config.TextColumn("label_tg_style", width="medium"),
        "label_fluortag_style": st.column_config.TextColumn("label_fluortag_style", width="medium"),
        "label_fluororganelle_style": st.column_config.TextColumn("label_fluororganelle_style", width="medium"),
    },
)

csv = df.to_csv(index=False).encode("utf-8")
st.download_button("Download CSV", data=csv, file_name="rois_flat.csv", mime="text/csv")
st.caption(f"{len(df):,} row(s) exported (exactly what you see)")