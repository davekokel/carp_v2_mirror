from __future__ import annotations

import os
import sys

import pandas as pd
from sqlalchemy import create_engine, text


def main() -> None:
    url = os.getenv("DB_URL")
    if not url:
        print("ERROR: DB_URL is not set in the environment.", file=sys.stderr)
        sys.exit(1)

    eng = create_engine(url, future=True)

    # 1) Find ROIs where roi_path is still placeholder-ish (NULL or equals roi_code)
    #    and v_imaging_clutches_rois.data_path gives us the real mount path.
    with eng.begin() as cx:
        df = pd.read_sql(
            text(
                """
                SELECT
                  v.roi_id,
                  v.clutch_code,
                  v.roi_code,
                  v.roi_path,
                  c.data_path
                FROM public.v11_imaging_roi_star v
                JOIN public.v_imaging_clutches_rois c
                  ON c.clutch_code = v.clutch_code
                 AND c.data_path   = v.roi_code
                WHERE (v.roi_path IS NULL OR v.roi_path = v.roi_code)
                """
            ),
            cx,
        )

    n = len(df)
    print(f"[INFO] candidate ROIs with placeholder roi_path + matching data_path: {n}")
    if n == 0:
        return

    # 2) Forward-fill roi_path on the base table imaging_roi_annotations
    updated = 0
    with eng.begin() as cx:
        for row in df.itertuples(index=False):
            cx.execute(
                text(
                    """
                    UPDATE public.imaging_roi_annotations
                    SET roi_path = :path
                    WHERE id = CAST(:rid AS uuid)
                    """
                ),
                {"path": row.data_path, "rid": row.roi_id},
            )
            updated += 1

    print(f"[OK] Updated roi_path for {updated} ROI(s).")


if __name__ == "__main__":
    main()
