#!/usr/bin/env python3
import os, sys, csv
from pathlib import Path
import psycopg

CONN = os.environ.get("CONN")
if not CONN:
    print("ERROR: Set CONN env var (e.g. postgres://...)", file=sys.stderr); sys.exit(1)

def load_allele_catalog(kit_dir: Path):
    csv_path = kit_dir / "03_transgene_alleles.csv"
    if not csv_path.exists():
        print(f"-- No 03_transgene_alleles.csv in: {kit_dir}")
        return
    print(f">> Upserting allele catalog from: {csv_path}")

    with psycopg.connect(CONN) as conn, conn.cursor() as cur:
        # Ensure target table exists (schema: base_code + allele_number as PK)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS public.transgene_alleles(
          transgene_base_code text NOT NULL,
          allele_number       text NOT NULL,
          description         text,
          PRIMARY KEY (transgene_base_code, allele_number)
        );
        """)

        # Stage CSV
        cur.execute("DROP TABLE IF EXISTS _stag_ta;")
        cur.execute("""
          CREATE TEMP TABLE _stag_ta(
            transgene_base_code  text,
            allele_number        text,
            description          text
          );
        """)
        with open(csv_path, newline='', encoding='utf-8') as f:
            r = csv.DictReader(f)
            with cur.copy(
                "COPY _stag_ta (transgene_base_code, allele_number, description) FROM STDIN"
            ) as cp:
                for row in r:
                    cp.write_row([
                        (row.get("transgene_base_code") or "").strip(),
                        (row.get("allele_number") or "").strip(),
                        (row.get("description") or "").strip(),
                    ])

        # Upsert
        cur.execute("""
        INSERT INTO public.transgene_alleles (transgene_base_code, allele_number, description)
        SELECT trim(transgene_base_code), trim(allele_number), NULLIF(trim(description),'')
        FROM _stag_ta
        WHERE COALESCE(transgene_base_code,'') <> '' AND COALESCE(allele_number,'') <> ''
        ON CONFLICT (transgene_base_code, allele_number) DO UPDATE
        SET description = EXCLUDED.description;
        """)

        # QA
        cur.execute("SELECT 'transgene_alleles', count(*) FROM public.transgene_alleles;")
        print("|".join(map(str, cur.fetchone())))
        conn.commit()

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: seedkit_load_allele_catalog.py /path/to/seedkit", file=sys.stderr)
        sys.exit(2)
    load_allele_catalog(Path(sys.argv[1]))
