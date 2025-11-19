#!/usr/bin/env python
from __future__ import annotations

import os
import csv
import uuid
from pathlib import Path
from typing import Dict, List

import psycopg2


ROOT = Path(__file__).resolve().parents[1]


def read_csv(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"CSV not found: {path}")
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def get_conn() -> psycopg2.extensions.connection:
    dsn = os.getenv("DB_URL")
    if not dsn:
        raise RuntimeError("DB_URL env var is not set")
    return psycopg2.connect(dsn)


def build_clutch_map(cur) -> Dict[str, str]:
    cur.execute(
        """
        SELECT clutch_code, id
        FROM public.clutches
        WHERE clutch_code LIKE 'IMG_CLT_%'
        """
    )
    return {code: str(cid) for code, cid in cur.fetchall()}


def main() -> None:
    csv_path = (
        ROOT
        / "seed_kits"
        / "legacy_import"
        / "working"
        / "imaging_clutch_memberships_from_sheet_draft.csv"
    )
    rows = read_csv(csv_path)

    conn = get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                clutch_map = build_clutch_map(cur)

                for row in rows:
                    clutch_code = (row.get("clutch_code") or "").strip()
                    clutch_id = clutch_map.get(clutch_code)
                    if not clutch_id:
                        continue

                    sheet_row_index_raw = row.get("sheet_row_index") or None
                    try:
                        sheet_row_index = int(sheet_row_index_raw) if sheet_row_index_raw else None
                    except ValueError:
                        sheet_row_index = None

                    date_born = row.get("date_born") or None
                    zf_f = row.get("zf_female_genotype_text") or None
                    zf_m = row.get("zf_male_genotype_text") or None
                    date_mount = row.get("date_mount") or None
                    mount_id = row.get("mount_id") or None
                    data_location = row.get("data_location") or None
                    row_pl = row.get("row_plasmids_text") or None
                    row_rna = row.get("row_rnas_text") or None
                    row_prot = row.get("row_proteins_text") or None
                    row_dye = row.get("row_dyes_text") or None

                    # avoid duplicate for same clutch_id + sheet_row_index
                    cur.execute(
                        """
                        SELECT 1
                        FROM public.imaging_clutch_memberships
                        WHERE clutch_id = %s
                          AND (sheet_row_index = %s OR %s IS NULL)
                        """,
                        (clutch_id, sheet_row_index, sheet_row_index),
                    )
                    if cur.fetchone():
                        continue

                    cur.execute(
                        """
                        INSERT INTO public.imaging_clutch_memberships (
                            id,
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
                            row_dyes_text
                        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        """,
                        (
                            str(uuid.uuid4()),
                            clutch_id,
                            sheet_row_index,
                            date_born,
                            zf_f,
                            zf_m,
                            date_mount,
                            mount_id,
                            data_location,
                            row_pl,
                            row_rna,
                            row_prot,
                            row_dye,
                        ),
                    )

        print("Done: imaging_clutch_memberships loaded.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
