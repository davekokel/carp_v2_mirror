from __future__ import annotations

import argparse
import os
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
    Same logic as v9_load_imaging_legacy_rois.py:
    plate_date + plate_id_filled -> 'YYYYMMDD-plateN'.
    """
    plate_date = row.get("plate_date")
    plate_id = row.get("plate_id_filled")
    if pd.isna(plate_date) or pd.isna(plate_id):
        raise ValueError(f"Missing plate_date/plate_id_filled for bruker_roi_id={row.get('bruker_roi_id')}")
    d_int = int(plate_date)
    plate_num = int(plate_id)
    return f"{d_int}-plate{plate_num}"


def build_orientation_map(sheet_path: str) -> pd.DataFrame:
    """
    Build a mapping from (date_mount_yyyymmdd, mount_id) -> mounting_orientation.
    """
    df_sheet = pd.read_excel(sheet_path)

    if "date_mount_yyyymmdd" in df_sheet.columns:
        df_sheet["date_mount_key"] = df_sheet["date_mount_yyyymmdd"]
    elif "date_mount" in df_sheet.columns:
        df_sheet["date_mount_key"] = (
            pd.to_datetime(df_sheet["date_mount"]).dt.strftime("%Y%m%d").astype(float)
        )
    else:
        raise SystemExit("Imaging sheet must have 'date_mount_yyyymmdd' or 'date_mount'")

    if "mount_id" not in df_sheet.columns:
        raise SystemExit("Imaging sheet must have 'mount_id'")
    if "Mounting Orientation" not in df_sheet.columns:
        raise SystemExit("Imaging sheet must have 'Mounting Orientation' column")

    df_sheet = df_sheet.copy()
    # mount_id may contain non-numeric junk; coerce to numeric and drop invalid rows
    df_sheet["mount_id"] = pd.to_numeric(df_sheet["mount_id"], errors="coerce")

    df_map = (
        df_sheet[["date_mount_key", "mount_id", "Mounting Orientation"]]
        .dropna(subset=["date_mount_key", "mount_id"])
        .copy()
    )
    df_map["orientation"] = df_map["Mounting Orientation"].astype(str).str.strip()
    df_map = df_map[["date_mount_key", "mount_id", "orientation"]].drop_duplicates()

    return df_map


def build_slot_orientation_df(roi_csv: str, orient_map: pd.DataFrame) -> pd.DataFrame:
    """
    For each (plate_code, slot_index), find the orientation using
    (date_mount_yyyymmdd, mount_id_inferred or mount_id) from the ROI CSV joined to the sheet.
    """
    df = pd.read_csv(roi_csv)
    required_cols = ["plate_date", "plate_id_filled", "slot_id_filled"]
    for c in required_cols:
        if c not in df.columns:
            raise SystemExit(f"Required column '{c}' not found in ROI CSV")

    if "date_mount_yyyymmdd" in df.columns:
        df["date_mount_key"] = df["date_mount_yyyymmdd"]
    else:
        df["date_mount_key"] = df["plate_date"]

    if "mount_id_inferred" in df.columns:
        mount_col = "mount_id_inferred"
    elif "mount_id" in df.columns:
        mount_col = "mount_id"
    else:
        raise SystemExit("ROI CSV must have 'mount_id_inferred' or 'mount_id' for orientation mapping")

    df = df.copy()
    df["mount_id"] = pd.to_numeric(df[mount_col], errors="coerce")
    df = df.dropna(subset=["mount_id"])
    df["plate_code"] = df.apply(plate_code_from_row, axis=1)
    df["slot_index"] = df["slot_id_filled"].astype(int)

    df_merge = df.merge(
        orient_map,
        on=["date_mount_key", "mount_id"],
        how="left",
    )

    slot_orient = (
        df_merge[["plate_code", "slot_index", "orientation"]]
        .dropna(subset=["orientation"])
        .drop_duplicates(subset=["plate_code", "slot_index"])
        .copy()
    )

    return slot_orient


def apply_slot_orientation(engine: Engine, slot_orient: pd.DataFrame) -> None:
    """
    Update public.imaging_slots.orientation for each (plate_code, slot_index) that has an orientation.
    """
    sql = text(
        """
        WITH plate AS (
          SELECT id AS plate_id
          FROM public.imaging_plates
          WHERE plate_code = :plate_code
        )
        UPDATE public.imaging_slots s
        SET orientation = :orientation
        FROM plate
        WHERE s.plate_id = plate.plate_id
          AND s.slot_index = :slot_index;
        """
    )

    with engine.begin() as conn:
        n = 0
        for _, row in slot_orient.iterrows():
            conn.execute(
                sql,
                {
                    "plate_code": row["plate_code"],
                    "slot_index": int(row["slot_index"]),
                    "orientation": row["orientation"],
                },
            )
            n += 1
        print(f"[OK] Applied orientation to {n} slot(s)")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backfill imaging_slots.orientation from imaging_sheet + legacy ROI CSV"
    )
    parser.add_argument("--sheet-xlsx", required=True, help="Path to imaging_sheet.xlsx")
    parser.add_argument("--roi-csv", required=True, help="Path to legacy_imaging_annotations_for_db_v9.csv")
    parser.add_argument("--db-url", help="Postgres DB URL (overrides DB_URL env var)")
    args = parser.parse_args()

    engine = get_engine(args.db_url)
    orient_map = build_orientation_map(args.sheet_xlsx)
    slot_orient = build_slot_orientation_df(args.roi_csv, orient_map)
    print(f"[INFO] Found {len(slot_orient)} (plate_code, slot_index, orientation) combinations")
    apply_slot_orientation(engine, slot_orient)


if __name__ == "__main__":
    main()
