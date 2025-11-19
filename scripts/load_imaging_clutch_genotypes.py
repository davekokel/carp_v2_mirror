#!/usr/bin/env python
from __future__ import annotations

import os
import csv
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


def main() -> None:
    csv_path = (
        ROOT
        / "seed_kits"
        / "legacy_import"
        / "working"
        / "imaging_clutches_from_sheet_draft.csv"
    )
    rows = read_csv(csv_path)

    conn = get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                for row in rows:
                    clutch_code = (row.get("clutch_code") or "").strip()
                    if not clutch_code:
                        continue

                    g_label = (row.get("genotype_cross_label") or "").strip() or None
                    g_bases = (row.get("genotype_base_codes") or "").strip() or None
                    g_alleles = (row.get("genotype_allele_codes") or "").strip() or None
                    g_pretty = (row.get("genotype_pretty") or "").strip() or None

                    cur.execute(
                        """
                        UPDATE public.clutches
                           SET genotype_cross_label  = %s,
                               genotype_base_codes   = %s,
                               genotype_allele_codes = %s,
                               genotype_pretty       = %s
                         WHERE clutch_code = %s
                        """,
                        (g_label, g_bases, g_alleles, g_pretty, clutch_code),
                    )

        print("Done: imaging clutch genotypes loaded into public.clutches.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
