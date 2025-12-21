#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import sqlalchemy as sa


def main() -> None:
    db_url = os.environ.get("DB_URL")
    if not db_url:
        raise SystemExit("[STOP] DB_URL must be set")

    eng = sa.create_engine(db_url)

    with eng.begin() as cx:
        n_total = cx.execute(sa.text("select count(*) from public.imaging_clutch_memberships")).scalar() or 0

        n_null_non_denoise = cx.execute(sa.text("""
            select count(*)
            from public.imaging_clutch_memberships m
            join public.imaging_roi_annotations ra on ra.slot_id = m.slot_id
            where m.treated_clutch_id is null
              and ra.roi_path not like '%/Denoising/%'
        """)).scalar() or 0

        n_missing_dataset_key_non_denoise = cx.execute(sa.text("""
            select count(*)
            from public.imaging_roi_annotations ra
            where ra.roi_path not like '%/Denoising/%'
              and regexp_match(ra.roi_path, '/(Aang_Foundation|Korra_Foundation|Exploratory_fish)/([0-9]{8}[^/]+)/') is null
        """)).scalar() or 0

    print(f"[QC] imaging_clutch_memberships total={int(n_total)}")
    print(f"[QC] untreated non-denoising memberships={int(n_null_non_denoise)}")
    print(f"[QC] ROI rows missing dataset_key (non-denoising)={int(n_missing_dataset_key_non_denoise)}")

    if int(n_null_non_denoise) != 0:
        raise SystemExit("[STOP] untreated non-denoising memberships remain; run overrides/applier")

    if int(n_missing_dataset_key_non_denoise) != 0:
        raise SystemExit("[STOP] non-denoising ROIs missing dataset_key; fix roi_path patterns or whitelist explicitly")

    print("[OK] legacy imaging treatment QC passed")


if __name__ == "__main__":
    main()
