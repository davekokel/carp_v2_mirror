from __future__ import annotations
import os
from pathlib import Path
from typing import Optional

import pandas as pd
from sqlalchemy import create_engine, text


BASE = Path(__file__).resolve().parents[1]
DEFAULT_CSV = BASE / "seed_kits" / "legacy_wrangling" / "working" / "imaging_clutch_memberships_manual.csv"


def main(csv_path: Optional[str] = None, import_batch_id: Optional[str] = None) -> None:
    db_url = os.environ.get("DB_URL")
    if not db_url:
        raise SystemExit("DB_URL is not set")

    path = Path(csv_path) if csv_path else DEFAULT_CSV
    if not path.exists():
        raise SystemExit(f"CSV not found: {path}")

    df = pd.read_csv(path)

    if "clutch_code" not in df.columns:
        raise SystemExit("CSV must include a 'clutch_code' column")

    if import_batch_id is None:
        import_batch_id = path.stem

    engine = create_engine(db_url)

    with engine.begin() as cx:
        clutch_codes = df["clutch_code"].dropna().unique().tolist()
        if not clutch_codes:
            print("[WARN] No clutch_code values found in CSV; nothing to do.")
            return

        rows = cx.execute(
            text(
                """
                SELECT clutch_code, id
                FROM public.clutches
                WHERE clutch_code = ANY(:codes)
                """
            ),
            {"codes": clutch_codes},
        ).mappings().all()
        code_to_id = {row["clutch_code"]: row["id"] for row in rows}

        print(f"[INFO] Resolved {len(code_to_id)} clutch_code(s) to clutch_id(s).")
        unknown = sorted(set(clutch_codes) - set(code_to_id))
        if unknown:
            print(f"[WARN] {len(unknown)} clutch_code(s) not found in clutches; skipping those rows.")
            for code in unknown[:20]:
                print(f"  - {code}")

        cx.execute(
            text(
                """
                DELETE FROM public.imaging_clutch_memberships
                WHERE import_batch_id = :batch
                """
            ),
            {"batch": import_batch_id},
        )
        print(f"[INFO] Deleted existing rows for import_batch_id={import_batch_id!r}.")

        inserted = 0
        for _, row in df.iterrows():
            clutch_code = row.get("clutch_code")
            clutch_id = code_to_id.get(clutch_code)
            if clutch_id is None:
                continue

            payload = {
                "clutch_id": clutch_id,
                "sheet_row_index": row.get("sheet_row_index"),
                "date_born": row.get("date_born"),
                "zf_female_genotype_text": row.get("zf_female_genotype_text"),
                "zf_male_genotype_text": row.get("zf_male_genotype_text"),
                "date_mount": row.get("date_mount"),
                "mount_id": row.get("mount_id"),
                "data_location": row.get("data_location"),
                "row_plasmids_text": row.get("row_plasmids_text"),
                "row_rnas_text": row.get("row_rnas_text"),
                "row_proteins_text": row.get("row_proteins_text"),
                "row_dyes_text": row.get("row_dyes_text"),
                "source_system": row.get("source_system", "legacy_sheet"),
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

        print(f"[OK] Inserted {inserted} row(s) into imaging_clutch_memberships for batch={import_batch_id!r}.")


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--csv", type=str, default=None, help="Path to clutch memberships CSV")
    p.add_argument("--batch", type=str, default=None, help="import_batch_id label")
    args = p.parse_args()
    main(csv_path=args.csv, import_batch_id=args.batch)
