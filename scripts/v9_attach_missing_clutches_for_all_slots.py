#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import argparse
from typing import List, Tuple, Optional

from sqlalchemy import create_engine, text

LCL_RE = re.compile(r"^LCL-(\d+)$", re.I)

def _max_lcl_num(cx) -> int:
    rows = cx.execute(text("SELECT clutch_code FROM public.clutches WHERE clutch_code LIKE 'LCL-%'")).fetchall()
    m = 0
    for (cc,) in rows:
        if not cc:
            continue
        s = str(cc).strip()
        mm = LCL_RE.match(s)
        if not mm:
            continue
        try:
            n = int(mm.group(1))
            if n > m:
                m = n
        except Exception:
            continue
    return m

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", default="legacy_attach_missing_slots_v4")
    args = ap.parse_args()

    db_url = os.environ.get("DB_URL")
    if not db_url:
        raise SystemExit("[STOP] DB_URL is not set")

    eng = create_engine(db_url)

    find_missing = text("""
      WITH roi_slots AS (
        SELECT
          s.id AS slot_id,
          p.plate_code,
          s.slot_index,
          count(ira.id) AS n_rois
        FROM public.imaging_roi_annotations ira
        JOIN public.imaging_slots s ON s.id = ira.slot_id
        JOIN public.imaging_plates p ON p.id = s.plate_id
        WHERE ira.roi_path IS NOT NULL
          AND (
            ira.roi_path ILIKE '%/Aang_Foundation/%'
            OR ira.roi_path ILIKE '%/Korra_Foundation/%'
          )
        GROUP BY s.id, p.plate_code, s.slot_index
      ),
      missing AS (
        SELECT
          rs.slot_id,
          rs.plate_code,
          rs.slot_index,
          rs.n_rois
        FROM roi_slots rs
        LEFT JOIN public.imaging_clutch_memberships m
          ON m.slot_id = rs.slot_id
        WHERE m.clutch_id IS NULL
      )
      SELECT slot_id::text, plate_code, slot_index, n_rois
      FROM missing
      ORDER BY plate_code, slot_index;
    """)

    insert_clutch = text("""
      INSERT INTO public.clutches (
        clutch_code,
        legacy_clutch_key,
        clutch_date,
        estimated_egg_count,
        notes,
        source_system,
        import_batch_id
      )
      VALUES (
        :clutch_code,
        :legacy_clutch_key,
        NULL,
        :estimated_egg_count,
        :notes,
        'legacy_imaging',
        :import_batch_id
      )
      RETURNING id::text;
    """)

    delete_membership = text("""
      DELETE FROM public.imaging_clutch_memberships
      WHERE slot_id = CAST(:slot_id AS uuid);
    """)

    insert_membership = text("""
      INSERT INTO public.imaging_clutch_memberships (slot_id, clutch_id, treated_clutch_id)
      VALUES (CAST(:slot_id AS uuid), CAST(:clutch_id AS uuid), NULL);
    """)

    with eng.begin() as cx:
        rows = cx.execute(find_missing).fetchall()
        if not rows:
            print("[OK] No ROI slots missing clutch_id. Nothing to do.")
            return

        start = _max_lcl_num(cx)
        made: List[Tuple[str, int, str]] = []

        for i, (slot_id, plate_code, slot_index, n_rois) in enumerate(rows, start=1):
            clutch_code = f"LCL-{start + i:04d}"
            legacy_key = f"{plate_code}|slot{int(slot_index)}"
            notes = f"auto-attach: slot had ROIs but no clutch_id | n_rois={int(n_rois)} | batch={args.batch}"

            clutch_id = cx.execute(
                insert_clutch,
                {
                    "clutch_code": clutch_code,
                    "legacy_clutch_key": legacy_key,
                    "estimated_egg_count": int(n_rois) if n_rois is not None else 1,
                    "notes": notes,
                    "import_batch_id": args.batch,
                },
            ).scalar()

            cx.execute(delete_membership, {"slot_id": slot_id})
            cx.execute(insert_membership, {"slot_id": slot_id, "clutch_id": clutch_id})

            made.append((plate_code, int(slot_index), clutch_code))

    print("[OK] Created + linked clutches for missing ROI slots:", len(made))
    for plate_code, slot_index, clutch_code in made[:50]:
        print(f"{plate_code}\tslot{slot_index}\t{clutch_code}")
    if len(made) > 50:
        print(f"... ({len(made)-50} more)")

if __name__ == "__main__":
    main()
