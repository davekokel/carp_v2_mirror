from __future__ import annotations

import argparse
import os
import re
from typing import Optional

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


def get_engine(db_url: Optional[str]) -> Engine:
    url = db_url or os.environ.get("DB_URL")
    if not url:
        raise SystemExit("DB_URL must be provided via --db-url or environment variable DB_URL")
    print(f"DB_URL={url}")
    return create_engine(url)


def plate_code_from_row(row: pd.Series) -> str:
    """
    Build plate_code from plate_date + plate_id_filled, e.g.
    plate_date=20250721, plate_id_filled=65 -> '20250721-plate65'.
    """
    plate_date = row.get("plate_date")
    plate_id = row.get("plate_id_filled")
    if pd.isna(plate_date) or pd.isna(plate_id):
        raise ValueError(f"Missing plate_date/plate_id_filled for bruker_roi_id={row.get('bruker_roi_id')}")
    d_int = int(plate_date)
    plate_num = int(plate_id)
    return f"{d_int}-plate{plate_num}"


def experiment_date_from_plate_date(plate_date: float) -> Optional[str]:
    if pd.isna(plate_date):
        return None
    d_int = int(plate_date)
    year = d_int // 10000
    month = (d_int % 10000) // 100
    day = d_int % 100
    return f"{year:04d}-{month:02d}-{day:02d}"

EXPERIMENT_FOLDER_RE = re.compile(r"/(20\d{6}_[^/]+)/")


def experiment_name_from_roi_path(roi_path: object) -> Optional[str]:
    """
    Extract experiment folder token like '20251106_mem-mito' from a ROI path.
    Returns None if not found.
    """
    if roi_path is None:
        return None
    s = str(roi_path)
    if not s or s.lower() in ("nan", "none"):
        return None
    m = EXPERIMENT_FOLDER_RE.search(s)
    if not m:
        return None
    v = m.group(1).strip()
    return v or None


def upsert_imaging_plates(df: pd.DataFrame, engine: Engine) -> None:
    df = df.copy()
    df["plate_code"] = df.apply(plate_code_from_row, axis=1)
    df["experiment_date"] = df["plate_date"].apply(experiment_date_from_plate_date)

    # Prefer explicit dataset_slug if present, otherwise derive from roi_dir/roi_path.
    # v9 compat CSVs usually don't have dataset_slug, so roi_dir is the source of truth.
    experiment_name_col = "dataset_slug" if "dataset_slug" in df.columns else None

    df["experiment_name_inferred"] = df["roi_dir"].apply(experiment_name_from_roi_path) if "roi_dir" in df.columns else None

    cols = ["plate_code", "experiment_date"]
    if experiment_name_col:
        cols.append(experiment_name_col)
    cols.append("experiment_name_inferred")

    plates = df[cols].drop_duplicates(subset=["plate_code"]).copy()

    def pick_name(row: pd.Series) -> Optional[str]:
        v = row.get(experiment_name_col) if experiment_name_col else None
        if v is not None:
            s = str(v).strip()
            if s and s.lower() not in ("nan", "none"):
                return s
        v2 = row.get("experiment_name_inferred")
        if v2 is not None:
            s2 = str(v2).strip()
            if s2 and s2.lower() not in ("nan", "none"):
                return s2
        return None

    plates["experiment_name"] = plates.apply(pick_name, axis=1)

    sql = text(
        """
        INSERT INTO public.imaging_plates (
            plate_code,
            experiment_date,
            experiment_name,
            scope_name,
            scope_settings,
            plate_note
        )
        VALUES (
            :plate_code,
            :experiment_date,
            :experiment_name,
            NULL,
            NULL,
            NULL
        )
        ON CONFLICT (plate_code) DO UPDATE
        SET experiment_date = COALESCE(EXCLUDED.experiment_date, public.imaging_plates.experiment_date),
            experiment_name = COALESCE(EXCLUDED.experiment_name, public.imaging_plates.experiment_name)
        """
    )

    with engine.begin() as conn:
        for _, row in plates.iterrows():
            conn.execute(
                sql,
                {
                    "plate_code": row["plate_code"],
                    "experiment_date": row["experiment_date"],
                    "experiment_name": row.get("experiment_name"),
                },
            )


def upsert_imaging_slots(df: pd.DataFrame, engine: Engine) -> None:
    if "slot_id_filled" not in df.columns:
        raise SystemExit("Required column 'slot_id_filled' not found in CSV")

    df = df.copy()
    df["plate_code"] = df.apply(plate_code_from_row, axis=1)
    df["slot_index"] = df["slot_id_filled"].astype(int)
    # use a simple label like 'slotN'
    df["slot_label"] = df["slot_index"].apply(lambda i: f"slot{i}")

    slots = df[["plate_code", "slot_index", "slot_label"]].drop_duplicates(
        subset=["plate_code", "slot_index"]
    )

    sql = text(
        """
        WITH plate AS (
          SELECT id AS plate_id
          FROM public.imaging_plates
          WHERE plate_code = :plate_code
        )
        INSERT INTO public.imaging_slots (
            plate_id,
            slot_index,
            slot_label,
            well_row,
            well_col,
            slot_note
        )
        SELECT
            plate_id,
            :slot_index,
            :slot_label,
            NULL,
            NULL,
            NULL
        FROM plate
        ON CONFLICT (plate_id, slot_index) DO UPDATE
        SET slot_label = EXCLUDED.slot_label
        """
    )

    with engine.begin() as conn:
        for _, row in slots.iterrows():
            conn.execute(
                sql,
                {
                    "plate_code": row["plate_code"],
                    "slot_index": int(row["slot_index"]),
                    "slot_label": row["slot_label"],
                },
            )


def insert_imaging_rois(df: pd.DataFrame, engine: Engine) -> None:
    required_cols = [
        "plate_date",
        "plate_id_filled",
        "slot_id_filled",
        "roi_index_within_slot",
        "roi_dir",
        "bruker_roi_id",
    ]
    for col in required_cols:
        if col not in df.columns:
            raise SystemExit(f"Required column '{col}' not found in CSV")

    df = df.copy()
    df["plate_code"] = df.apply(plate_code_from_row, axis=1)
    df["slot_index"] = df["slot_id_filled"].astype(int)
    df["roi_index_int"] = df["roi_index_within_slot"].astype(int)

    # anatomy note if present
    if "roi_anatomy" in df.columns:
        df["roi_note_anatomy"] = df["roi_anatomy"]
    else:
        df["roi_note_anatomy"] = None

    # use bruker_roi_id as stable identifier, but keep roi_path as the real filesystem path
    df["roi_code"] = df["bruker_roi_id"].astype(str)
    df["roi_path"] = df["roi_dir"].astype(str)

    # normalize pandas stringy nulls
    bad = df["roi_path"].isin(["nan", "None", ""])
    df.loc[bad, "roi_path"] = df.loc[bad, "roi_code"]

    sql = text(
        """
        WITH plate AS (
          SELECT id AS plate_id
          FROM public.imaging_plates
          WHERE plate_code = :plate_code
        ),
        slot AS (
          SELECT s.id AS slot_id
          FROM public.imaging_slots s
          JOIN plate p ON p.plate_id = s.plate_id
          WHERE s.slot_index = :slot_index
        )
        INSERT INTO public.imaging_roi_annotations (
            slot_id,
            roi_index_within_slot,
            roi_code,
            roi_path,
            roi_note_anatomy
        )
        SELECT
            slot_id,
            :roi_index_within_slot,
            :roi_code,
            :roi_path,
            :roi_note_anatomy
        FROM slot
        ON CONFLICT (slot_id, roi_index_within_slot) DO UPDATE
        SET roi_path         = EXCLUDED.roi_path,
            roi_note_anatomy = EXCLUDED.roi_note_anatomy
        """
    )

    with engine.begin() as conn:
        for _, row in df.iterrows():
            params = {
                "plate_code": row["plate_code"],
                "slot_index": int(row["slot_index"]),
                "roi_index_within_slot": int(row["roi_index_int"]),
                "roi_code": row["roi_code"],
                "roi_path": row["roi_path"],
                "roi_note_anatomy": row["roi_note_anatomy"],
            }
            conn.execute(sql, params)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Load legacy imaging ROIs into lean imaging tables (imaging_plates, imaging_slots, imaging_roi_annotations)."
    )
    parser.add_argument("--csv", required=True, help="Path to legacy_imaging_annotations_for_db_v9.csv")
    parser.add_argument("--db-url", help="Postgres DB URL (overrides DB_URL env var)")
    args = parser.parse_args()

    engine = get_engine(args.db_url)
    df = pd.read_csv(args.csv, low_memory=False)

    # Minimal contract for the lean imaging loader
    needed = [
        "plate_date",
        "plate_id_filled",
        "slot_id_filled",
        "roi_index_within_slot",
        "roi_dir",
        "bruker_roi_id",
    ]
    missing = [c for c in needed if c not in df.columns]
    if missing:
        raise SystemExit(f"ROI CSV missing required columns: {missing}")

    # Core upserts (plates -> slots -> rois)
    upsert_imaging_plates(df, engine)
    upsert_imaging_slots(df, engine)
    insert_imaging_rois(df, engine)

    # QC counts
    with engine.begin() as cx:
        n_plates = cx.execute(text("SELECT count(*) FROM public.imaging_plates")).scalar()
        n_slots  = cx.execute(text("SELECT count(*) FROM public.imaging_slots")).scalar()
        n_rois   = cx.execute(text("SELECT count(*) FROM public.imaging_roi_annotations")).scalar()

    print(f"[OK] v9_load_imaging_legacy_rois: plates={int(n_plates)}, slots={int(n_slots)}, rois={int(n_rois)}")


if __name__ == "__main__":
    main()
