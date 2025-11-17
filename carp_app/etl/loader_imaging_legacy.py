from __future__ import annotations

from pathlib import Path
from typing import Optional, List, Dict
import uuid

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from carp_app.etl.loaders import get_engine_from_env


def _norm_str(v) -> str:
    if v is None:
        return ""
    return str(v).strip()


def _uuid_for_plate(plate_code: str) -> str:
    if not plate_code:
        # Fallback: random UUID if no plate_code, but we expect plate_code to be present
        return str(uuid.uuid4())
    # Deterministic UUID from plate_code
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, plate_code))


def load_imaging_from_legacy_standard(
    slots_csv: str | Path,
    rois_csv: str | Path,
    engine: Optional[Engine] = None,
) -> dict:
    """
    Load imaging_slots and imaging_rois from standard_from_legacy CSVs.

    slots CSV expected columns:
      - plate_code
      - slot_code
      - legacy_fish_label
      - fish_code
      - imaging_nickname
      - timepoint
      - notes

    rois CSV expected columns:
      - plate_code
      - slot_code
      - roi_code
      - roi_index
      - roi_name
      - roi_dir
      - date_imaged
      - notes
    """
    slots_path = Path(slots_csv)
    rois_path = Path(rois_csv)
    if not slots_path.exists():
        raise FileNotFoundError(f"slots CSV not found: {slots_path}")
    if not rois_path.exists():
        raise FileNotFoundError(f"rois CSV not found: {rois_path}")

    df_slots = pd.read_csv(slots_path)
    df_rois = pd.read_csv(rois_path)
    if df_slots.empty:
        return {
            "slot_rows": 0,
            "slots_inserted": 0,
            "roi_rows": len(df_rois),
            "rois_inserted": 0,
            "warnings": ["slots CSV is empty"],
        }

    df_slots = df_slots.copy()
    df_slots.columns = [str(c).strip().lower() for c in df_slots.columns]
    for col in ["plate_code", "slot_code", "legacy_fish_label", "fish_code", "imaging_nickname", "timepoint", "notes"]:
        if col in df_slots.columns:
            df_slots[col] = df_slots[col].apply(_norm_str)
        else:
            df_slots[col] = ""

    df_rois = df_rois.copy()
    df_rois.columns = [str(c).strip().lower() for c in df_rois.columns]
    for col in ["plate_code", "slot_code", "roi_code", "roi_name", "roi_dir", "date_imaged", "notes"]:
        if col in df_rois.columns:
            df_rois[col] = df_rois[col].apply(_norm_str)
        else:
            df_rois[col] = ""

    if engine is None:
        engine = get_engine_from_env()

    warnings: List[str] = []
    slots_inserted = 0
    rois_inserted = 0

    with engine.begin() as cx:
        # Start with a clean imaging layer (legacy only)
        cx.execute(
            text(
                """
                TRUNCATE TABLE
                  public.imaging_rois,
                  public.imaging_slots
                RESTART IDENTITY CASCADE;
                """
            )
        )

        fish_ids: Dict[str, str] = {}
        slot_ids: Dict[str, str] = {}
        plate_ids: Dict[str, str] = {}

        # Cache fish_instance ids by fish_code
        fish_rows = cx.execute(
            text(
                """
                SELECT id, fish_code
                FROM public.fish_instance
                """
            )
        ).mappings().all()
        for r in fish_rows:
            fish_ids[str(r["fish_code"])] = str(r["id"])

        # Compute plate_ids from plate_code and upsert into public.plates
        plate_codes = df_slots["plate_code"].dropna().unique().tolist()
        for pc in plate_codes:
            pc_str = _norm_str(pc)
            if not pc_str:
                continue
            pid = _uuid_for_plate(pc_str)
            plate_ids[pc_str] = pid

            cx.execute(
                text(
                    """
                    INSERT INTO public.plates (id, plate_code)
                    VALUES (:id, :code)
                    ON CONFLICT (plate_code) DO NOTHING
                    """
                ),
                {"id": pid, "code": pc_str},
            )

        # Insert slots
        for _, row in df_slots.iterrows():
            plate_code = row.get("plate_code", "") or ""
            slot_code = row.get("slot_code", "") or ""
            fish_code = row.get("fish_code", "") or ""
            imaging_nickname = row.get("imaging_nickname", "") or ""
            notes = row.get("notes", "") or ""

            if not slot_code:
                warnings.append("Skipping slot row with empty slot_code")
                continue

            plate_id = None
            if plate_code:
                plate_id = plate_ids.get(plate_code)
            if not plate_id:
                plate_id = _uuid_for_plate(plate_code)
                warnings.append(
                    f"Slot {slot_code!r}: missing/blank plate_code; using synthetic plate_id."
                )

            fish_id = None
            if fish_code:
                fish_id = fish_ids.get(fish_code)
                if not fish_id:
                    warnings.append(
                        f"Slot {slot_code!r}: fish_code={fish_code!r} not found in fish_instance."
                    )

            slot_row = cx.execute(
                text(
                    """
                    WITH new_id AS (
                      SELECT gen_random_uuid() AS id
                    )
                    INSERT INTO public.imaging_slots
                      (id, plate_id, slot_label, fish_id, experiment_nickname, notes)
                    SELECT
                      nid.id,
                      :plate_id,
                      :slot_label,
                      :fish_id,
                      NULLIF(:exp_nick,''),
                      NULLIF(:notes,'')
                    FROM new_id nid
                    RETURNING id
                    """
                ),
                {
                    "plate_id": plate_id,
                    "slot_label": slot_code,
                    "fish_id": fish_id,
                    "exp_nick": imaging_nickname,
                    "notes": notes,
                },
            ).mappings().first()

            if not slot_row:
                warnings.append(f"Failed to insert imaging_slot for slot_code={slot_code!r}")
                continue

            sid = str(slot_row["id"])
            slot_ids[slot_code] = sid
            slots_inserted += 1

        # Insert rois, skipping duplicate (slot_code, roi_index) pairs
        seen_roi_keys: set[tuple[str, int | None]] = set()

        for _, row in df_rois.iterrows():
            slot_code = row.get("slot_code", "") or ""
            roi_index = row.get("roi_index", None)
            roi_name = row.get("roi_name", "") or ""
            roi_dir = row.get("roi_dir", "") or ""
            notes = row.get("notes", "") or ""

            if not slot_code:
                warnings.append("Skipping ROI row with empty slot_code")
                continue

            slot_id = slot_ids.get(slot_code)
            if not slot_id:
                warnings.append(
                    f"Skipping ROI {roi_name!r}: slot_code={slot_code!r} not found among inserted slots."
                )
                continue

            try:
                roi_index_int = int(roi_index)
            except Exception:
                roi_index_int = None

            roi_key = (slot_code, roi_index_int)
            if roi_key in seen_roi_keys:
                warnings.append(
                    f"Skipping duplicate ROI for slot_code={slot_code!r}, roi_index={roi_index_int!r}."
                )
                continue
            seen_roi_keys.add(roi_key)

            cx.execute(
                text(
                    """
                    WITH new_id AS (
                      SELECT gen_random_uuid() AS id
                    )
                    INSERT INTO public.imaging_rois
                      (id, slot_id, roi_index, roi_name, data_path, channel_info, notes)
                    SELECT
                      nid.id,
                      :slot_id,
                      :roi_index,
                      NULLIF(:roi_name,''),
                      NULLIF(:data_path,''),
                      '{}'::jsonb,
                      NULLIF(:notes,'')
                    FROM new_id nid
                    """
                ),
                {
                    "slot_id": slot_id,
                    "roi_index": roi_index_int,
                    "roi_name": roi_name,
                    "data_path": roi_dir,
                    "notes": notes,
                },
            )
            rois_inserted += 1

    return {
        "slot_rows": len(df_slots),
        "slots_inserted": slots_inserted,
        "roi_rows": len(df_rois),
        "rois_inserted": rois_inserted,
        "warnings": warnings,
    }
