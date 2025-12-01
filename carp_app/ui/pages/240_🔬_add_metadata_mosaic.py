# carp_app/ui/pages/240_🔬_add_metadata_mosaic.py

from __future__ import annotations

import os
import sys
import pathlib
from datetime import date
from typing import Optional, Dict, Any, List, Tuple

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
    def require_app_unlock():
        ...

from carp_app.ui.lib.app_ctx import get_engine

# v11 views
V_PLATE_SLOT_OVERVIEW_V11 = "public.v11_imaging_plate_slot_overview"
V_CLUTCH_STAR = "public.v11_clutch_star"

sb, session, user = require_auth()
require_email_otp()
try:
    require_app_unlock()
except Exception:
    pass

st.set_page_config(
    page_title="CARP — 🔬 Add imaging metadata",
    page_icon="🔬",
    layout="wide",
)
st.title("🔬 Add imaging metadata (v11 imaging, mosaic)")


@st.cache_resource(show_spinner=False)
def _eng() -> Engine:
    url = os.getenv("DB_URL")
    if not url:
        st.error("DB_URL is not set")
        st.stop()
    return get_engine()


def eng() -> Engine:
    return _eng()


def _norm(s: str | None) -> Optional[str]:
    s = (s or "").strip()
    return s or None


def _rollup(series: pd.Series) -> str:
    vals = [str(x) for x in series.tolist()]
    vals = [v for v in vals if v and v.lower() != "nan"]
    return ", ".join(sorted(set(vals))) if vals else ""


def _ensure_view(name: str) -> None:
    schema, tbl = name.split(".", 1)
    with eng().begin() as cx:
        df = pd.read_sql(
            text(
                """
                SELECT 1
                FROM information_schema.views
                WHERE table_schema = :s AND table_name = :n
                UNION ALL
                SELECT 1
                FROM pg_catalog.pg_matviews
                WHERE schemaname = :s AND matviewname = :n
                LIMIT 1
                """
            ),
            cx,
            params={"s": schema, "n": tbl},
        )
    if df.empty:
        st.error(f"Required view not found: {name}")
        st.stop()


_ensure_view(V_PLATE_SLOT_OVERVIEW_V11)
_ensure_view(V_CLUTCH_STAR)

# ──────────────────────────────────────────────────────────────────────────────
# Step 1 — Filter plates & slots
# ──────────────────────────────────────────────────────────────────────────────

st.subheader("Step 1 — Filter plates & slots", anchor=False)

with st.form("filter_form", clear_on_submit=False):
    c1, c2, c3, c4 = st.columns([3, 1.5, 1.5, 0.7])
    with c1:
        q_raw = st.text_input(
            "Search (plate / slot / experiment / notes / clutch / treatment / genotype)",
            "",
        )
    with c2:
        plate_raw = st.text_input("Plate code contains", "")
    with c3:
        date_raw = st.text_input("Experiment date (YYYY-MM-DD)", "")
    with c4:
        lim = int(
            st.number_input(
                "Limit (plates)",
                min_value=10,
                max_value=2000,
                value=500,
                step=50,
            )
        )
    _ = st.form_submit_button("Apply")

q = _norm(q_raw)
plate_filter = _norm(plate_raw)
date_filter: Optional[date] = None
if date_raw:
    try:
        date_filter = date.fromisoformat(date_raw)
    except ValueError:
        st.warning("Date must be YYYY-MM-DD.")
        st.stop()

where: List[str] = ["1=1"]
params: Dict[str, Any] = {"lim": lim}

if q:
    params["q"] = f"%{q}%"
    where.append(
        "("
        "  plate_code ILIKE :q "
        " OR slot_label ILIKE :q "
        " OR experiment_name ILIKE :q "
        " OR plate_note ILIKE :q "
        " OR clutch_code ILIKE :q "
        " OR treat_code ILIKE :q "
        " OR genotype_code ILIKE :q "
        ")"
    )

if plate_filter:
    params["p"] = f"%{plate_filter}%"
    where.append("plate_code ILIKE :p")

if date_filter:
    params["d"] = date_filter.isoformat()
    where.append("experiment_date = :d")

sql = text(
    f"""
    SELECT
      plate_id,
      plate_code,
      experiment_date,
      experiment_name,
      plate_note,
      slot_id,
      slot_label,
      slot_index,
      slot_note,
      n_rois,
      clutch_code,
      treat_code,
      treat_text,
      genotype_code,
      genotype_pretty
    FROM {V_PLATE_SLOT_OVERVIEW_V11}
    WHERE {" AND ".join(where)}
    ORDER BY experiment_date DESC NULLS LAST,
             plate_code, slot_index, slot_label
    LIMIT :lim
"""
)

with eng().begin() as cx:
    df_plate_slots = pd.read_sql(sql, cx, params=params)

for col in df_plate_slots.select_dtypes(include=["object", "string"]).columns:
    df_plate_slots[col] = df_plate_slots[col].astype("string").fillna("")

if df_plate_slots.empty:
    st.info("No matching plates/slots.")
    st.stop()

st.caption(
    f"{df_plate_slots['plate_code'].nunique()} plate(s), "
    f"{df_plate_slots['slot_id'].notna().sum()} slot rows"
)

# ──────────────────────────────────────────────────────────────────────────────
# Step 1a — Select a plate
# ──────────────────────────────────────────────────────────────────────────────

st.subheader("Step 1a — Select a plate", anchor=False)

plates_df = (
    df_plate_slots.groupby(["plate_id", "plate_code"], as_index=False)
    .agg(
        experiment_date=("experiment_date", "first"),
        experiment_name=("experiment_name", "first"),
        plate_note=("plate_note", "first"),
        clutch_codes=("clutch_code", _rollup),
        genotype_codes=("genotype_code", _rollup),
        treatment_codes=("treat_code", _rollup),
    )
    .sort_values(["experiment_date", "plate_code"], ascending=[False, True])
    .reset_index(drop=True)
)

plates_view = plates_df.copy()
plates_view.insert(0, "✓ Select", False)

plates_grid = st.data_editor(
    plates_view[
        [
            "✓ Select",
            "plate_code",
            "experiment_date",
            "experiment_name",
            "clutch_codes",
            "genotype_codes",
            "treatment_codes",
            "plate_note",
        ]
    ],
    hide_index=True,
    use_container_width=True,
    num_rows="fixed",
    column_config={
        "✓ Select":        st.column_config.CheckboxColumn("✓", default=False),
        "plate_code":      st.column_config.TextColumn("Plate", disabled=True),
        "experiment_date": st.column_config.DateColumn("Date", disabled=True),
        "experiment_name": st.column_config.TextColumn("Experiment", disabled=True),
        "clutch_codes":    st.column_config.TextColumn("Clutch code(s)", disabled=True, width="stretch"),
        "genotype_codes":  st.column_config.TextColumn("Genotype code(s)", disabled=True, width="stretch"),
        "treatment_codes": st.column_config.TextColumn("Treatment code(s)", disabled=True, width="stretch"),
        "plate_note":      st.column_config.TextColumn("Plate note (view)", disabled=True, width="stretch"),
    },
)

sel_mask = plates_grid["✓ Select"] == True
if not sel_mask.any():
    st.caption("Select a plate above to proceed.")
    st.stop()

plate_row = plates_df.loc[sel_mask[sel_mask].index[0]]
selected_plate_id = plate_row["plate_id"]
selected_plate_code = plate_row["plate_code"]

st.caption(f"Selected plate: **{selected_plate_code}**")

# ──────────────────────────────────────────────────────────────────────────────
# Plate note editor
# ──────────────────────────────────────────────────────────────────────────────

plate_note_input = st.text_area(
    "Plate note (stored in imaging_plates.plate_note)",
    value=plate_row["plate_note"] or "",
)

if st.button("💾 Save plate note"):
    with eng().begin() as cx:
        cx.execute(
            text(
                """
                UPDATE public.imaging_plates
                SET plate_note = :note
                WHERE id = :pid
                """
            ),
            {"note": plate_note_input or None, "pid": selected_plate_id},
        )
    st.success("Saved plate note.")

base_path = st.text_input(
    "Base path for ROI files (optional; used only for path suggestions)",
    value=st.session_state.get("imaging_base_path", ""),
    key="imaging_base_path",
).strip()

df_plate_only = df_plate_slots[df_plate_slots["plate_id"] == selected_plate_id].reset_index(drop=True)

# ──────────────────────────────────────────────────────────────────────────────
# Step 1b — Select slot(s) on this plate
# ──────────────────────────────────────────────────────────────────────────────

st.subheader("Step 1b — Select slot(s) on this plate", anchor=False)

df_slots = df_plate_only.copy()

# orientation column may or may not exist; load defensively
with eng().begin() as cx:
    try:
        df_orient = pd.read_sql(
            text(
                """
                SELECT id::text AS slot_id,
                       orientation
                FROM public.imaging_slots
                WHERE plate_id = CAST(:pid AS uuid)
                """
            ),
            cx,
            params={"pid": selected_plate_id},
        )
    except Exception:
        df_orient = pd.DataFrame(columns=["slot_id", "orientation"])

if not df_orient.empty:
    df_slots = df_slots.merge(df_orient, on="slot_id", how="left")
else:
    df_slots["orientation"] = ""

df_slots["orientation"] = df_slots["orientation"].fillna("")

roi_counts_key = f"roi_counts::{selected_plate_id}"
if roi_counts_key not in st.session_state:
    st.session_state[roi_counts_key] = {
        row["slot_label"]: int(row["n_rois"])
        for _, row in df_slots.iterrows()
    }
roi_counts: Dict[str, int] = st.session_state[roi_counts_key]

base_counts_by_slot: Dict[str, int] = {
    row["slot_label"]: int(row["n_rois"])
    for _, row in df_slots.iterrows()
}

df_slots["planned_n_rois"] = df_slots["slot_label"].map(
    lambda sl: roi_counts.get(sl, 0)
).astype(int)

slots_view = df_slots[
    [
        "slot_id",
        "slot_label",
        "slot_index",
        "orientation",
        "planned_n_rois",
        "n_rois",
        "clutch_code",
        "treat_code",
        "genotype_code",
    ]
].copy()
slots_view.insert(0, "✓ Select", False)

slots_grid = st.data_editor(
    slots_view,
    key="slots_grid",
    hide_index=True,
    num_rows="fixed",
    column_config={
        "✓ Select":            st.column_config.CheckboxColumn("✓"),
        "slot_label":          st.column_config.TextColumn("Slot", disabled=True),
        "slot_index":          st.column_config.NumberColumn("Index", disabled=True),
        "orientation":         st.column_config.TextColumn("Orientation", disabled=False),
        "planned_n_rois":      st.column_config.NumberColumn("Planned #ROIs", disabled=True),
        "n_rois":              st.column_config.NumberColumn("Existing #ROIs", disabled=True),
        "clutch_code":         st.column_config.TextColumn("Parent clutch", disabled=True),
        "treat_code":          st.column_config.TextColumn("Treatment", disabled=True),
        "genotype_code":       st.column_config.TextColumn("Genotype", disabled=True),
    },
)

selected_slots = slots_grid[slots_grid["✓ Select"] == True]["slot_label"].tolist()

c1, c2, c3 = st.columns(3)
with c1:
    if st.button("💾 Save slot metadata (orientation)"):
        with eng().begin() as cx:
            for _, row in slots_grid.iterrows():
                if not row["✓ Select"]:
                    continue
                cx.execute(
                    text(
                        """
                        UPDATE public.imaging_slots
                        SET orientation = :o
                        WHERE id = :sid
                        """
                    ),
                    {
                        "o": row["orientation"] or None,
                        "sid": row["slot_id"],
                    },
                )
        st.success("Saved slot metadata.")

with c2:
    if st.button("➕ Add ROI to selected slots"):
        for sl in selected_slots:
            roi_counts[sl] = roi_counts.get(sl, 0) + 1
        st.session_state[roi_counts_key] = roi_counts
        st.rerun()

with c3:
    if st.button("➖ Remove ROI from selected slots"):
        for sl in selected_slots:
            existing = base_counts_by_slot.get(sl, 0)
            roi_counts[sl] = max(existing, roi_counts.get(sl, 0) - 1)
        st.session_state[roi_counts_key] = roi_counts
        st.rerun()

slot_index_map = {
    row["slot_label"]: int(row["slot_index"])
    for _, row in df_slots.iterrows()
}
slot_id_map = {
    row["slot_label"]: row["slot_id"]
    for _, row in df_slots.iterrows()
}

if selected_slots:
    st.caption(f"Selected slots: {', '.join(selected_slots)}")
else:
    st.caption("No slots selected yet — Step 2 will show an empty ROI table until you select slots and add ROIs.")

# ──────────────────────────────────────────────────────────────────────────────
# Step 2 — ROI rows for selected slots
# ──────────────────────────────────────────────────────────────────────────────

st.subheader("Step 2 — ROI rows for selected slots", anchor=False)

slots_for_display = sorted(df_slots["slot_label"].unique().tolist())

# Pull existing ROIs by slot_id and join labels/indexes client-side
if slots_for_display:
    slot_ids_for_query = [slot_id_map[sl] for sl in slots_for_display if sl in slot_id_map]
    if slot_ids_for_query:
        sql_rois = text(
            """
            SELECT
              id::text          AS roi_id,
              slot_id::text     AS slot_id,
              roi_index_within_slot,
              roi_code,
              roi_path,
              roi_note_anatomy
            FROM public.imaging_roi_annotations
            WHERE slot_id::text = ANY(:slot_ids)
            ORDER BY slot_id, roi_index_within_slot, roi_code, id
            """
        )
        with eng().begin() as cx:
            df_rois_raw = pd.read_sql(
                sql_rois,
                cx,
                params={"slot_ids": slot_ids_for_query},
            )
    else:
        df_rois_raw = pd.DataFrame(
            columns=["roi_id", "slot_id", "roi_index_within_slot", "roi_code", "roi_path", "roi_note_anatomy"]
        )
else:
    df_rois_raw = pd.DataFrame(
        columns=["roi_id", "slot_id", "roi_index_within_slot", "roi_code", "roi_path", "roi_note_anatomy"]
    )

for c in df_rois_raw.select_dtypes(include=["object", "string"]).columns:
    df_rois_raw[c] = df_rois_raw[c].astype("string").fillna("")

# join slot_label / slot_index for display
if not df_rois_raw.empty:
    df_rois_raw = df_rois_raw.merge(
        df_slots[["slot_id", "slot_label", "slot_index"]],
        on="slot_id",
        how="left",
    )

# ensure annotation_notes / qc_flag columns exist (added by migration)
existing_ids = df_rois_raw["roi_id"].dropna().tolist() if not df_rois_raw.empty else []
if existing_ids:
    with eng().begin() as cx:
        df_ann = pd.read_sql(
            text(
                """
                SELECT id::text AS roi_id,
                       annotation_notes,
                       qc_flag
                FROM public.imaging_roi_annotations
                WHERE id::text = ANY(:ids)
                """
            ),
            cx,
            params={"ids": existing_ids},
        )
    df_rois_raw = df_rois_raw.merge(df_ann, on="roi_id", how="left")
else:
    df_rois_raw["annotation_notes"] = ""
    df_rois_raw["qc_flag"] = ""

existing_map: Dict[Tuple[str, int], Dict[str, Any]] = {}
for _, r in df_rois_raw.iterrows():
    idx = int(r.get("roi_index_within_slot") or 0)
    sl = r.get("slot_label")
    if idx <= 0 or not sl:
        continue
    key = (sl, idx)
    existing_map[key] = r.to_dict()

rows: List[Dict[str, Any]] = []

for sl in slots_for_display:
    existing = base_counts_by_slot.get(sl, 0)
    planned = max(existing, roi_counts.get(sl, existing))
    for i in range(1, planned + 1):
        key = (sl, i)
        if key in existing_map:
            r = existing_map[key]
            roi_id = r["roi_id"]
            roi_code = r["roi_code"]
            roi_path = r["roi_path"]
            anat = r.get("roi_note_anatomy") or ""
            notes = r.get("annotation_notes") or ""
            qc = r.get("qc_flag") or ""
        else:
            roi_id = ""
            roi_code = f"{sl}-{i:02d}"
            if base_path:
                roi_path = f"{base_path.rstrip('/')}/{selected_plate_code}/{roi_code}"
            else:
                roi_path = roi_code
            anat = ""
            notes = ""
            qc = ""

        rows.append(
            {
                "roi_id": roi_id,
                "plate_code": selected_plate_code,
                "slot_label": sl,
                "slot_index": slot_index_map.get(sl, 0),
                "roi_index_within_slot": i,
                "roi_code": roi_code,
                "roi_path": roi_path,
                "roi_note_anatomy": anat,
                "annotation_notes": notes,
                "qc_flag": qc,
                "✓ Delete": False,
            }
        )

if rows:
    df_anno = pd.DataFrame(rows)
else:
    df_anno = pd.DataFrame(
        columns=[
            "✓ Delete",
            "plate_code",
            "slot_label",
            "slot_index",
            "roi_index_within_slot",
            "roi_code",
            "roi_path",
            "roi_note_anatomy",
            "annotation_notes",
            "qc_flag",
            "roi_id",
        ]
    )

st.caption(f"Planned ROI rows (existing + new): {len(df_anno)}")

display_df = df_anno.copy()

edited_df = st.data_editor(
    display_df[
        [
            "✓ Delete",
            "plate_code",
            "slot_label",
            "slot_index",
            "roi_index_within_slot",
            "roi_code",
            "roi_path",
            "roi_note_anatomy",
            "annotation_notes",
            "qc_flag",
        ]
    ],
    key="roi_rows_editor",
    hide_index=True,
    num_rows="fixed",
    column_config={
        "✓ Delete":            st.column_config.CheckboxColumn("Del", default=False),
        "plate_code":          st.column_config.TextColumn("Plate", disabled=True),
        "slot_label":          st.column_config.TextColumn("Slot", disabled=True),
        "slot_index":          st.column_config.NumberColumn("Slot idx", disabled=True),
        "roi_index_within_slot": st.column_config.NumberColumn("ROI idx", disabled=True),
        "roi_code":            st.column_config.TextColumn("ROI code", disabled=True),
        "roi_path":            st.column_config.TextColumn("ROI path", disabled=False, width="stretch"),
        "roi_note_anatomy":    st.column_config.TextColumn("Anatomy note", disabled=False, width="stretch"),
        "annotation_notes":    st.column_config.TextColumn("Notes", disabled=False, width="stretch"),
        "qc_flag":             st.column_config.TextColumn("QC", disabled=False),
    },
)

save_df = df_anno.copy()
for col in ["✓ Delete", "roi_path", "roi_note_anatomy", "annotation_notes", "qc_flag"]:
    if col in edited_df.columns:
        save_df[col] = edited_df[col].values

c_save, c_dl = st.columns(2)
with c_save:
    if st.button("💾 Save ROI metadata"):
        n_upd = n_ins = n_del = 0
        with eng().begin() as cx:
            for _, row in save_df.iterrows():
                delete_flag = bool(row.get("✓ Delete"))
                roi_id = (row.get("roi_id") or "").strip()
                sl = row.get("slot_label")
                slot_id = slot_id_map.get(sl)
                if not slot_id:
                    continue

                if delete_flag:
                    if roi_id:
                        cx.execute(
                            text(
                                "DELETE FROM public.imaging_roi_annotations WHERE id = :id"
                            ),
                            {"id": roi_id},
                        )
                        n_del += 1
                    continue

                params = {
                    "slot_id": slot_id,
                    "roi_index": int(row.get("roi_index_within_slot") or 0),
                    "roi_code": row.get("roi_code") or None,
                    "roi_path": row.get("roi_path") or None,
                    "roi_note_anatomy": row.get("roi_note_anatomy") or None,
                    "annotation_notes": row.get("annotation_notes") or None,
                    "qc_flag": row.get("qc_flag") or None,
                }

                if roi_id:
                    cx.execute(
                        text(
                            """
                            UPDATE public.imaging_roi_annotations
                            SET roi_path = :roi_path,
                                roi_note_anatomy = :roi_note_anatomy,
                                annotation_notes = :annotation_notes,
                                qc_flag = :qc_flag
                            WHERE id = :id
                            """
                        ),
                        {**params, "id": roi_id},
                    )
                    n_upd += 1
                else:
                    cx.execute(
                        text(
                            """
                            INSERT INTO public.imaging_roi_annotations (
                                slot_id,
                                roi_index_within_slot,
                                roi_code,
                                roi_path,
                                roi_note_anatomy,
                                annotation_notes,
                                qc_flag
                            )
                            VALUES (
                                :slot_id,
                                :roi_index,
                                :roi_code,
                                :roi_path,
                                :roi_note_anatomy,
                                :annotation_notes,
                                :qc_flag
                            )
                            """
                        ),
                        params,
                    )
                    n_ins += 1

        st.success(
            f"Saved ROI metadata ({n_upd} updated, {n_ins} inserted, {n_del} deleted)."
        )

with c_dl:
    st.download_button(
        "⬇︎ Download ROI metadata snapshot (CSV)",
        data=save_df.to_csv(index=False).encode("utf-8"),
        file_name=f"{selected_plate_code}_roi_metadata_snapshot.csv",
        mime="text/csv",
    )