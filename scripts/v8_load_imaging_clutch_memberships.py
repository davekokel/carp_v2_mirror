import os
import argparse
from typing import Dict, Tuple

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


def get_engine() -> Engine:
    db_url = os.environ.get("DB_URL")
    if not db_url:
        raise RuntimeError("DB_URL environment variable is not set")
    print(f"DB_URL={db_url}")
    return create_engine(db_url)


def load_clutch_ids(engine: Engine) -> Dict[str, str]:
    """
    clutch_code -> clutch_id
    Restrict to legacy_imaging clutches to avoid collisions.
    """
    sql = text(
        """
        SELECT id::text, clutch_code
        FROM public.clutches
        WHERE source_system = 'legacy_imaging'
        """
    )
    with engine.begin() as cx:
        rows = cx.execute(sql).fetchall()

    mapping: Dict[str, str] = {}
    for cid, code in rows:
        if code:
            mapping[str(code)] = cid
    return mapping


def load_slot_ids(engine: Engine) -> Dict[Tuple[str, str], str]:
    """
    (plate_code, slot_label) -> slot_id
    imaging_plates.plate_code should match plate_id_filled
    imaging_slots.slot_label should match slot_id_filled
    """
    sql = text(
        """
        SELECT s.id::text AS slot_id,
               p.plate_code,
               s.slot_label
        FROM public.imaging_slots s
        JOIN public.imaging_plates p ON p.id = s.plate_id
        """
    )
    with engine.begin() as cx:
        rows = cx.execute(sql).fetchall()

    mapping: Dict[Tuple[str, str], str] = {}
    for slot_id, plate_code, slot_label in rows:
        key = (str(plate_code), str(slot_label))
        mapping[key] = slot_id
    return mapping


def main() -> None:
    parser = argparse.ArgumentParser(
        description="v8: load imaging_clutch_memberships from legacy_clutch_memberships.csv"
    )
    parser.add_argument(
        "--csv",
        default="seed_kits/legacy_wrangling/working/legacy_clutch_memberships.csv",
        help="Path to legacy_clutch_memberships.csv",
    )
    args = parser.parse_args()

    csv_path = args.csv
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"legacy_clutch_memberships CSV not found: {csv_path}")

    df = pd.read_csv(csv_path)

    required_cols = {
        "clutch_code",
        "plate_id_filled",
        "slot_id_filled",
    }
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"legacy_clutch_memberships CSV missing columns: {missing}")

    # group ROI-level rows to one record per (clutch, plate, slot)
    grouped = (
        df.groupby(["clutch_code", "plate_id_filled", "slot_id_filled"])
        .size()
        .reset_index(name="roi_count")
    )

    engine = get_engine()
    clutch_ids = load_clutch_ids(engine)
    slot_ids = load_slot_ids(engine)

    insert_sql = text(
        """
        INSERT INTO public.imaging_clutch_memberships (
          clutch_id,
          slot_id,
          role,
          embryo_count,
          mount_notes,
          created_by
        )
        VALUES (
          :clutch_id,
          :slot_id,
          :role,
          :embryo_count,
          :mount_notes,
          :created_by
        )
        ON CONFLICT (clutch_id, slot_id) DO UPDATE SET
          embryo_count = EXCLUDED.embryo_count
        """
    )

    created_by = (
        os.environ.get("USER")
        or os.environ.get("USERNAME")
        or "legacy_imaging_loader"
    )

    inserted = 0
    skipped_missing_clutch = 0
    skipped_missing_slot = 0

    with engine.begin() as cx:
        for _, row in grouped.iterrows():
            clutch_code = str(row["clutch_code"]).strip()
            plate_code = str(row["plate_id_filled"]).strip()
            slot_label = str(row["slot_id_filled"]).strip()
            roi_count = int(row["roi_count"])

            if not clutch_code:
                continue

            clutch_id = clutch_ids.get(clutch_code)
            if clutch_id is None:
                print(
                    f"[WARN] No clutch_id for clutch_code='{clutch_code}'; "
                    f"skipping plate={plate_code}, slot={slot_label}"
                )
                skipped_missing_clutch += 1
                continue

            key = (plate_code, slot_label)
            slot_id = slot_ids.get(key)
            if slot_id is None:
                print(
                    f"[WARN] No imaging_slot for plate='{plate_code}', slot='{slot_label}'; "
                    f"skipping clutch_code='{clutch_code}'"
                )
                skipped_missing_slot += 1
                continue

            cx.execute(
                insert_sql,
                {
                    "clutch_id": clutch_id,
                    "slot_id": slot_id,
                    "role": "primary",
                    "embryo_count": roi_count,
                    "mount_notes": None,
                    "created_by": created_by,
                },
            )
            inserted += 1

    print(f"imaging_clutch_memberships: inserted/updated={inserted}")
    print(f"  skipped (missing clutch): {skipped_missing_clutch}")
    print(f"  skipped (missing slot):   {skipped_missing_slot}")


if __name__ == "__main__":
    main()
