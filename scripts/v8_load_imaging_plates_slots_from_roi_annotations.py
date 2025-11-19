import os
import argparse
import datetime as dt
from typing import Dict

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


def get_engine() -> Engine:
    db_url = os.environ.get("DB_URL")
    if not db_url:
        raise RuntimeError("DB_URL environment variable is not set")
    print(f"DB_URL={db_url}")
    return create_engine(db_url)


def parse_experiment_date(plate_code: str):
    # expects leading YYYYMMDD-...
    try:
        prefix = plate_code[:8]
        return dt.datetime.strptime(prefix, "%Y%m%d").date()
    except Exception:
        return None


def parse_slot_index(slot_label: str):
    # expects ...-slotNN
    if "-slot" not in slot_label:
        return None
    suffix = slot_label.split("-slot", 1)[1]
    try:
        return int(suffix)
    except Exception:
        return None


def load_existing_plates(engine: Engine) -> Dict[str, str]:
    sql = text("SELECT id::text, plate_code FROM public.imaging_plates")
    with engine.begin() as cx:
        rows = cx.execute(sql).fetchall()
    return {str(code): sid for sid, code in rows if code}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="v8: load imaging_plates and imaging_slots from imaging_roi_annotations_AUTO.csv"
    )
    parser.add_argument(
        "--roi-csv",
        default="seed_kits/legacy_wrangling/working/imaging_roi_annotations_AUTO.csv",
        help="Path to imaging_roi_annotations_AUTO.csv",
    )
    args = parser.parse_args()

    csv_path = args.roi_csv
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"ROI AUTO CSV not found: {csv_path}")

    df = pd.read_csv(csv_path)

    required_cols = {"plate_id_filled", "slot_id_filled"}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"ROI AUTO CSV missing columns: {missing}")

    engine = get_engine()

    # ----- plates -----
    df_plates = (
        df[["plate_id_filled"]]
        .dropna()
        .drop_duplicates()
        .rename(columns={"plate_id_filled": "plate_code"})
    )

    existing_plates = load_existing_plates(engine)
    insert_plate_sql = text(
        """
        INSERT INTO public.imaging_plates (
          plate_code,
          experiment_date
        )
        VALUES (:plate_code, :experiment_date)
        ON CONFLICT (plate_code) DO NOTHING
        RETURNING id::text
        """
    )

    plates_inserted = 0

    with engine.begin() as cx:
        for _, row in df_plates.iterrows():
            plate_code = str(row["plate_code"]).strip()
            if not plate_code:
                continue
            if plate_code in existing_plates:
                continue

            exp_date = parse_experiment_date(plate_code)
            sid = cx.execute(
                insert_plate_sql,
                {"plate_code": plate_code, "experiment_date": exp_date},
            ).scalar()

            if sid:
                existing_plates[plate_code] = sid
                plates_inserted += 1

    # refresh existing_plates in case some were created without RETURNING in earlier runs
    existing_plates = load_existing_plates(engine)

    # ----- slots -----
    df_slots = (
        df[["plate_id_filled", "slot_id_filled"]]
        .dropna()
        .drop_duplicates()
        .rename(
            columns={
                "plate_id_filled": "plate_code",
                "slot_id_filled": "slot_label",
            }
        )
    )

    insert_slot_sql = text(
        """
        INSERT INTO public.imaging_slots (
          plate_id,
          slot_index,
          slot_label
        )
        VALUES (
          :plate_id,
          :slot_index,
          :slot_label
        )
        ON CONFLICT (slot_label) DO NOTHING
        """
    )

    slots_inserted = 0
    skipped_missing_plate = 0

    with engine.begin() as cx:
        for _, row in df_slots.iterrows():
            plate_code = str(row["plate_code"]).strip()
            slot_label = str(row["slot_label"]).strip()
            if not plate_code or not slot_label:
                continue

            plate_id = existing_plates.get(plate_code)
            if plate_id is None:
                print(
                    f"[WARN] No imaging_plate for plate_code='{plate_code}'; "
                    f"skipping slot_label='{slot_label}'"
                )
                skipped_missing_plate += 1
                continue

            slot_index = parse_slot_index(slot_label)

            cx.execute(
                insert_slot_sql,
                {
                    "plate_id": plate_id,
                    "slot_index": slot_index,
                    "slot_label": slot_label,
                },
            )
            slots_inserted += 1

    print(f"imaging_plates: inserted={plates_inserted}")
    print(f"imaging_slots:  inserted={slots_inserted}, skipped_missing_plate={skipped_missing_plate}")


if __name__ == "__main__":
    main()
