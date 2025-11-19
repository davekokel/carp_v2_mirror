from __future__ import annotations
import os
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text


BASE = Path(__file__).resolve().parents[1]
CSV_PATH = BASE / "seed_kits" / "legacy_wrangling" / "working" / "legacy_clutches.csv"


def main() -> None:
    db_url = os.environ.get("DB_URL")
    if not db_url:
        raise SystemExit("DB_URL is not set")

    if not CSV_PATH.exists():
        raise SystemExit(f"CSV not found: {CSV_PATH}")

    df = pd.read_csv(CSV_PATH)

    required = {"clutch_code", "date_born"}
    missing = required - set(df.columns)
    if missing:
        raise SystemExit(f"legacy_clutches.csv missing required columns: {sorted(missing)}")

    if "import_batch_id" in df.columns and df["import_batch_id"].notna().any():
        import_batch_id = str(df["import_batch_id"].dropna().iloc[0])
    else:
        import_batch_id = "legacy_clutch_inference_2025-11-18"

    engine = create_engine(db_url)

    with engine.begin() as cx:
        cx.execute(
            text(
                """
                ALTER TABLE public.clutches
                ADD COLUMN IF NOT EXISTS source_system text
                """
            )
        )
        cx.execute(
            text(
                """
                ALTER TABLE public.clutches
                ADD COLUMN IF NOT EXISTS import_batch_id text
                """
            )
        )

        cx.execute(
            text(
                """
                DELETE FROM public.clutches
                WHERE source_system = 'legacy_imaging'
                  AND import_batch_id = :batch
                """
            ),
            {"batch": import_batch_id},
        )
        print(f"[INFO] Deleted existing legacy clutches for import_batch_id={import_batch_id!r}.")

        inserted = 0
        with_missing_date = 0

        for _, row in df.iterrows():
            clutch_code = row.get("clutch_code")
            date_born = row.get("date_born")

            if pd.isna(date_born):
                print(f"[WARN] Inserting legacy clutch {clutch_code!r} with UNKNOWN date_born (clutch_date=NULL).")
                clutch_date = None
                with_missing_date += 1
            else:
                clutch_date = date_born

            payload = {
                "clutch_code": clutch_code,
                "clutch_date": clutch_date,  # may be None
                "estimated_egg_count": row.get("roi_count"),
                "genotype_cross_label": None,
                "genotype_base_codes": None,
                "genotype_allele_codes": None,
                "genotype_pretty": None,
                "notes": f"legacy_imaging; roi_count={row.get('roi_count')}",
                "source_system": "legacy_imaging",
                "import_batch_id": import_batch_id,
            }

            cx.execute(
                text(
                    """
                    INSERT INTO public.clutches (
                        clutch_code,
                        clutch_date,
                        estimated_egg_count,
                        genotype_cross_label,
                        genotype_base_codes,
                        genotype_allele_codes,
                        genotype_pretty,
                        notes,
                        source_system,
                        import_batch_id
                    )
                    VALUES (
                        :clutch_code,
                        :clutch_date,
                        :estimated_egg_count,
                        :genotype_cross_label,
                        :genotype_base_codes,
                        :genotype_allele_codes,
                        :genotype_pretty,
                        :notes,
                        :source_system,
                        :import_batch_id
                    )
                    """
                ),
                payload,
            )
            inserted += 1

        print(f"[OK] Inserted {inserted} legacy clutch row(s) for batch={import_batch_id!r}.")
        if with_missing_date:
            print(f"[WARN] {with_missing_date} clutch(es) inserted with NULL clutch_date (unknown date_born).")


if __name__ == "__main__":
    main()
