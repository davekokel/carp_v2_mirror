#!/usr/bin/env python3
from __future__ import annotations

import os
from sqlalchemy import create_engine, text


def main() -> None:
    db_url = os.environ.get("DB_URL")
    if not db_url:
        raise SystemExit("[STOP] DB_URL is not set")

    eng = create_engine(db_url)

    with eng.begin() as cx:
        total = int(cx.execute(text("SELECT count(*) FROM public.imaging_clutch_memberships")).scalar() or 0)

        n_with_treated = int(
            cx.execute(
                text("SELECT count(*) FROM public.imaging_clutch_memberships WHERE treated_clutch_id IS NOT NULL")
            ).scalar()
            or 0
        )

        untreated = total - n_with_treated

        has_dataset_key = bool(
            cx.execute(
                text(
                    """
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'v11_roi_flat_table_display'
                      AND column_name = 'dataset_key'
                    LIMIT 1
                    """
                )
            ).scalar()
        )

        missing_dataset_key = None
        if has_dataset_key:
            missing_dataset_key = int(
                cx.execute(
                    text(
                        """
                        SELECT count(*)
                        FROM public.v11_roi_flat_table_display
                        WHERE coalesce(btrim(dataset_key),'') = ''
                        """
                    )
                ).scalar()
                or 0
            )

    print(f"[QC] imaging_clutch_memberships total={total}")
    print(f"[QC] memberships_with_treated_clutch_id={n_with_treated}")
    print(f"[QC] untreated_memberships={untreated}")

    if has_dataset_key:
        print(f"[QC] ROI rows missing dataset_key={missing_dataset_key}")
        if int(missing_dataset_key or 0) != 0:
            raise SystemExit("[STOP] ROI rows missing dataset_key remain; fix linking keys upstream")
    else:
        print("[QC] dataset_key column not present on v11_roi_flat_table_display; skipping that check")

    print("[OK] QC passed (untreated memberships allowed; dataset_key check conditional).")


if __name__ == "__main__":
    main()
