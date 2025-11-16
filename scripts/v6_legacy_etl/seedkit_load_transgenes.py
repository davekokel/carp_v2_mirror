#!/usr/bin/env python3
import os, sys, csv
from pathlib import Path
import psycopg

CONN = os.environ.get("CONN")
if not CONN:
    print("ERROR: Set CONN env var (e.g. postgres://…)", file=sys.stderr)
    sys.exit(1)

def upsert_transgenes(conn, csv_path: Path):
    if not csv_path.exists():
        print(f"ERROR: file not found: {csv_path}", file=sys.stderr)
        sys.exit(1)
    print(f">> Upserting transgenes from: {csv_path}")

    with conn.cursor() as cur:
        # conflict target for transgenes by *base* code
        cur.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS ux_transgenes_base
            ON public.transgenes(transgene_base_code)
        """)

        # stage
        cur.execute("DROP TABLE IF EXISTS _stag_transgenes")
        cur.execute("""
            CREATE TEMP TABLE _stag_transgenes(
              transgene_base_code  text,
              name                 text,
              description          text
            )
        """)
        with open(csv_path, newline='', encoding='utf-8') as f:
            r = csv.DictReader(f)
            rows = [(row.get('transgene_base_code',''), row.get('name',''), row.get('description','')) for row in r]
        with cur.copy("COPY _stag_transgenes (transgene_base_code, name, description) FROM STDIN") as cp:
            for a,b,c in rows:
                cp.write_row([a,b,c])

        # upsert
        cur.execute("""
            INSERT INTO public.transgenes(code, name, description, transgene_base_code)
            SELECT trim(transgene_base_code), name, description, trim(transgene_base_code)
            FROM _stag_transgenes
            WHERE COALESCE(transgene_base_code,'') <> ''
            ON CONFLICT (transgene_base_code) DO UPDATE
            SET  code        = COALESCE(EXCLUDED.code, public.transgenes.code),
                 name        = EXCLUDED.name,
                 description = EXCLUDED.description
        """)
        cur.execute("SELECT 'transgenes', count(*) FROM public.transgenes")
        print("|".join(map(str, cur.fetchone())))
    conn.commit()

def upsert_transgene_alleles(conn, csv_path: Path):
    """
    Loads 03_transgene_alleles.csv with columns:
      - transgene_base_code
      - allele_number
      - description
    Keys by (transgene_base_code, allele_number).
    """
    if not csv_path.exists():
        print(f"-- No allele CSV found, skipping: {csv_path}")
        return

    print(f">> Upserting transgene alleles from: {csv_path}")
    with conn.cursor() as cur:
        # ensure table/unique composite key exist (safe if already present)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS public.transgene_alleles(
              transgene_base_code text NOT NULL,
              allele_number       text NOT NULL,
              description         text,
              PRIMARY KEY (transgene_base_code, allele_number)
            )
        """)

        # stage
        cur.execute("DROP TABLE IF EXISTS _stag_tg_alleles")
        cur.execute("""
            CREATE TEMP TABLE _stag_tg_alleles(
              transgene_base_code  text,
              allele_number        text,
              description          text
            )
        """)
        with open(csv_path, newline='', encoding='utf-8') as f:
            r = csv.DictReader(f)
            rows = [(row.get('transgene_base_code',''),
                     row.get('allele_number',''),
                     row.get('description','')) for row in r]
        with cur.copy("COPY _stag_tg_alleles (transgene_base_code, allele_number, description) FROM STDIN") as cp:
            for a,b,c in rows:
                cp.write_row([a,b,c])

        # upsert by composite key
        cur.execute("""
            INSERT INTO public.transgene_alleles(transgene_base_code, allele_number, description)
            SELECT trim(transgene_base_code), trim(allele_number), description
            FROM _stag_tg_alleles
            WHERE COALESCE(transgene_base_code,'') <> '' AND COALESCE(allele_number,'') <> ''
            ON CONFLICT (transgene_base_code, allele_number) DO UPDATE
            SET description = EXCLUDED.description
        """)
        cur.execute("SELECT 'transgene_alleles', count(*) FROM public.transgene_alleles")
        print("|".join(map(str, cur.fetchone())))
    conn.commit()

def load_kit(kit_dir: Path):
    tg_csv   = kit_dir / "02_transgenes.csv"
    alle_csv = kit_dir / "03_transgene_alleles.csv"
    with psycopg.connect(CONN) as conn:
        upsert_transgenes(conn, tg_csv)
        upsert_transgene_alleles(conn, alle_csv)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: seedkit_load_transgenes.py /path/to/seedkit_folder", file=sys.stderr)
        sys.exit(2)
    kit = Path(sys.argv[1])
    if not kit.is_dir():
        print(f"ERROR: not a folder: {kit}", file=sys.stderr)
        sys.exit(2)
    load_kit(kit)