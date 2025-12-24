from __future__ import annotations

import argparse
import os
from typing import Optional, Any

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


def get_engine(db_url: Optional[str]) -> Engine:
    url = db_url or os.environ.get("DB_URL")
    if not url:
        raise SystemExit("DB_URL must be provided via --db-url or environment variable DB_URL")
    print(f"DB_URL={url}")
    return create_engine(url)


def _scalar(v: Any) -> Any:
    if isinstance(v, pd.Series):
        vv = v.dropna()
        return vv.iloc[0] if len(vv) else pd.NA
    if isinstance(v, (list, tuple)):
        return v[0] if len(v) else pd.NA
    return v


def _yyyymmdd(v: Any) -> str | None:
    v = _scalar(v)
    if v is None or (isinstance(v, float) and pd.isna(v)) or (isinstance(v, str) and v.strip() == ""):
        return None
    s = str(v).strip()
    if s.endswith(".0") and s[:-2].isdigit():
        s = s[:-2]
    s = s.replace("-", "")
    if len(s) == 8 and s.isdigit():
        return s
    dt = pd.to_datetime(v, errors="coerce")
    if pd.isna(dt):
        return None
    return dt.strftime("%Y%m%d")


def plate_code_from_row(row: pd.Series) -> str:
    plate_date = _yyyymmdd(row.get("plate_date"))
    plate_id = _scalar(row.get("plate_id_filled"))

    if not plate_date or pd.isna(plate_id):
        raise ValueError(
            f"Missing plate_date/plate_id_filled for bruker_roi_id={_scalar(row.get('bruker_roi_id'))}"
        )

    plate_num = int(float(plate_id))
    return f"{plate_date}-plate{plate_num}"


def build_orientation_map(sheet_path: str) -> pd.DataFrame:
    df_sheet = pd.read_excel(sheet_path)

    if "date_mount_yyyymmdd" in df_sheet.columns:
        df_sheet["date_mount_key"] = df_sheet["date_mount_yyyymmdd"].map(_yyyymmdd)
    elif "date_mount" in df_sheet.columns:
        df_sheet["date_mount_key"] = df_sheet["date_mount"].map(_yyyymmdd)
    else:
        raise SystemExit("Imaging sheet must have 'date_mount_yyyymmdd' or 'date_mount'")

    if "mount_id" not in df_sheet.columns:
        raise SystemExit("Imaging sheet must have 'mount_id'")
    if "Mounting Orientation" not in df_sheet.columns:
        raise SystemExit("Imaging sheet must have 'Mounting Orientation' column")

    df_sheet = df_sheet.copy()
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
    df = pd.read_csv(roi_csv, low_memory=False)

    if df.columns.duplicated().any():
        df = df.loc[:, ~df.columns.duplicated()].copy()

    required_cols = ["plate_date", "plate_id_filled", "slot_id_filled"]
    for c in required_cols:
        if c not in df.columns:
            raise SystemExit(f"Required column '{c}' not found in ROI CSV")

    if "date_mount_yyyymmdd" in df.columns:
        df["date_mount_key"] = df["date_mount_yyyymmdd"].map(_yyyymmdd)
    else:
        df["date_mount_key"] = df["plate_date"].map(_yyyymmdd)

    if "mount_id_inferred" in df.columns:
        mount_col = "mount_id_inferred"
    elif "mount_id" in df.columns:
        mount_col = "mount_id"
    else:
        raise SystemExit("ROI CSV must have 'mount_id_inferred' or 'mount_id' for orientation mapping")

    df = df.copy()
    df["mount_id"] = pd.to_numeric(df[mount_col], errors="coerce")
    df = df.dropna(subset=["mount_id", "date_mount_key"])

    plate_date = df["plate_date"].map(_yyyymmdd)
    plate_id = pd.to_numeric(df["plate_id_filled"], errors="coerce")
    plate_id = plate_id.dropna().astype(int)
    df = df.loc[plate_id.index].copy()
    plate_date = plate_date.loc[df.index]
    df = df.loc[plate_date.notna()].copy()
    plate_date = plate_date.loc[df.index]
    df["plate_code"] = plate_date.astype("string") + "-plate" + pd.to_numeric(df["plate_id_filled"], errors="coerce").astype("Int64").astype("string")
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
