from __future__ import annotations
import os
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text


BASE = Path(__file__).resolve().parents[1]
CSV_PATH = BASE / "seed_kits" / "legacy_wrangling" / "working" / "legacy_clutch_memberships.csv"


def main() -> None:
    db_url = os.environ.get("DB_URL")
    if not db_url:
        raise SystemExit("DB_URL is not set")

    if not CSV_PATH.exists():
        raise SystemExit(f"CSV not found: {CSV_PATH}")

    df = pd.read_csv(CSV_PATH)

    required = {"clutch_code", "roi_code"}
    missing = required - set(df.columns)
    if missing:
        raise SystemExit(f"legacy_clutch_memberships.csv missing required columns: {sorted(missing)}")

    if "import_batch_id" in df.columns and df["import_batch_id"].notna().any():
        import_batch_id = str(df["import_batch_id"].dropna().iloc[0])
    else:
        import_batch_id = "legacy_clutch_inference_2025-11-18"

    engine = create_engine(db_url)

    with engine.begin() as cx:
        cx.execute(
            text(
                """
                ALTER TABLE public.imaging_clutch_memberships
                ADD COLUMN IF NOT EXISTS source_system text
                """
            )
        )
        cx.execute(
            text(
                """
                ALTER TABLE public.imaging_clutch_memberships
                ADD COLUMN IF NOT EXISTS import_batch_id text
                """
            )
        )

        clutch_codes = df["clutch_code"].dropna().unique().tolist()
        rows = cx.execute(
            text(
                """
                SELECT clutch_code, id
                FROM public.clutches
                WHERE clutch_code = ANY(:codes)
                  AND source_system = 'legacy_imaging'
                """
            ),
            {"codes": clutch_codes},
        ).mappings().all()
        code_to_id = {row["clutch_code"]: row["id"] for row in rows}

        if not code_to_id:
            raise SystemExit(
                "[ERROR] No clutch_code values from legacy_clutch_memberships.csv "
                "could be resolved in public.clutches for source_system='legacy_imaging'."
            )

        unknown = sorted(set(clutch_codes) - set(code_to_id))
        if unknown:
            print(
                f"[WARN] {len(unknown)} clutch_code(s) in memberships have no matching legacy clutch; "
                "memberships for them will be skipped. Examples:"
            )
            for code in unknown[:20]:
                print(f"  - {code}")

        print(f"[INFO] Will load memberships for {len(code_to_id)} clutch_code(s).")

        cx.execute(
            text(
                """
                DELETE FROM public.imaging_clutch_memberships
                WHERE source_system = 'legacy_imaging'
                  AND import_batch_id = :batch
                """
            ),
            {"batch": import_batch_id},
        )
        print(f"[INFO] Deleted existing legacy imaging_clutch_memberships for import_batch_id={import_batch_id!r}.")

        inserted = 0
        skipped = 0
        for _, row in df.iterrows():
            clutch_code = row.get("clutch_code")
            clutch_id = code_to_id.get(clutch_code)
            if clutch_id is None:
                skipped += 1
                continue

            raw_date_born = row.get("date_born")
            # convert NaN → None so Postgres sees NULL, not float
            date_born = None if pd.isna(raw_date_born) else raw_date_born

            payload = {
                "clutch_id": clutch_id,
                "sheet_row_index": None,
                "date_born": date_born,
                "zf_female_genotype_text": row.get("parent_female"),
                "zf_male_genotype_text": row.get("parent_male"),
                "date_mount": None,
                "mount_id": None,
                "data_location": row.get("roi_dir"),
                "row_plasmids_text": None,
                "row_rnas_text": None,
                "row_proteins_text": None,
                "row_dyes_text": None,
                "source_system": "legacy_imaging",
                "import_batch_id": import_batch_id,
            }

            cx.execute(
                text(
                    """
                    INSERT INTO public.imaging_clutch_memberships (
                        clutch_id,
                        sheet_row_index,
                        date_born,
                        zf_female_genotype_text,
                        zf_male_genotype_text,
                        date_mount,
                        mount_id,
                        data_location,
                        row_plasmids_text,
                        row_rnas_text,
                        row_proteins_text,
                        row_dyes_text,
                        source_system,
                        import_batch_id
                    )
                    VALUES (
                        :clutch_id,
                        :sheet_row_index,
                        :date_born,
                        :zf_female_genotype_text,
                        :zf_male_genotype_text,
                        :date_mount,
                        :mount_id,
                        :data_location,
                        :row_plasmids_text,
                        :row_rnas_text,
                        :row_proteins_text,
                        :row_dyes_text,
                        :source_system,
                        :import_batch_id
                    )
                    """
                ),
                payload,
            )
            inserted += 1

        print(f"[OK] Inserted {inserted} legacy imaging_clutch_memberships row(s) for batch={import_batch_id!r}.")
        if skipped:
            print(f"[WARN] Skipped {skipped} membership row(s) due to missing legacy clutch.")


if __name__ == "__main__":
    main()
