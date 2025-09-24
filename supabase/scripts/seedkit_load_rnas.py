#!/usr/bin/env python3
import os, sys, csv
from pathlib import Path
import psycopg

CONN = os.environ.get("CONN")
if not CONN:
    print("ERROR: Set CONN env var", file=sys.stderr); sys.exit(1)

def upsert_rnas(kit_dir: Path):
    csv_path = kit_dir / "04b_rnas.csv"
    if not csv_path.exists():
        print(f"-- No RNA CSV at {csv_path}; skipping.")
        return
    print(f">> Upserting RNAs from: {csv_path}")

    with psycopg.connect(CONN) as conn, conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS public.rnas(
              code text PRIMARY KEY,
              name text,
              description text
            )
        """)
        cur.execute("DROP TABLE IF EXISTS _stag_rnas")
        cur.execute("CREATE TEMP TABLE _stag_rnas(code text, name text, description text)")
        with open(csv_path, newline='', encoding='utf-8') as f:
            r = csv.DictReader(f)
            with cur.copy("COPY _stag_rnas(code, name, description) FROM STDIN") as cp:
                for row in r:
                    cp.write_row([
                        (row.get('rna_code') or row.get('code') or "").strip(),
                        (row.get('name') or "").strip(),
                        (row.get('description') or "").strip(),
                    ])
        cur.execute("""
            INSERT INTO public.rnas(code, name, description)
            SELECT trim(code), NULLIF(trim(name),''), NULLIF(trim(description),'') FROM _stag_rnas
            WHERE COALESCE(trim(code),'')<>''
            ON CONFLICT (code) DO UPDATE
            SET name=COALESCE(EXCLUDED.name, rnas.name),
                description=COALESCE(EXCLUDED.description, rnas.description)
        """)
        cur.execute("SELECT 'rnas', COUNT(*) FROM public.rnas")
        print("|".join(map(str, cur.fetchone())))
        conn.commit()

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: seedkit_load_rnas.py /path/to/seedkit", file=sys.stderr); sys.exit(2)
    upsert_rnas(Path(sys.argv[1]))
