#!/usr/bin/env python
from __future__ import annotations

import os
import csv
from pathlib import Path
from typing import List, Dict

import psycopg2


ROOT = Path(__file__).resolve().parents[1]


def get_conn() -> psycopg2.extensions.connection:
    dsn = os.getenv("DB_URL")
    if not dsn:
        raise RuntimeError("DB_URL env var is not set")
    return psycopg2.connect(dsn)


def main() -> None:
    out_path = (
        ROOT
        / "seed_kits"
        / "legacy_import"
        / "working"
        / "imaging_unmapped_treatments.csv"
    )
    conn = get_conn()
    try:
        with conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT
                  treat_code,
                  treat_text
                FROM public.v_imaging_clutches_treatments
                WHERE COALESCE(plasmid_base_codes, '') = ''
                  AND COALESCE(rna_base_codes, '') = ''
                  AND COALESCE(dye_base_codes, '') = ''
                ORDER BY treat_code;
                """
            )
            rows = cur.fetchall()
            cols = ["treat_code", "treat_text"]

        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(cols)
            for r in rows:
                w.writerow(r)

        print(f"[OK] Wrote {len(rows)} unmapped imaging treatments → {out_path}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
