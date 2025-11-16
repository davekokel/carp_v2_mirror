#!/usr/bin/env python3
import os, sys, csv
from pathlib import Path
import psycopg

CONN = os.environ.get("CONN")
if not CONN:
    print("ERROR: Set CONN env var (e.g. postgres://...)", file=sys.stderr); sys.exit(1)

def link_alleles(kit_dir: Path):
    # pick the CSV
    candidates = [
        kit_dir / "10_fish_transgene_alleles.csv",
        kit_dir / "fish_transgene_alleles.csv",
    ]
    csv_path = next((p for p in candidates if p.exists()), None)
    if not csv_path:
        print(f"-- No allele CSV in: {kit_dir}")
        return
    print(f">> Linking fish ↔ transgene alleles from: {csv_path}")

    with psycopg.connect(CONN) as conn, conn.cursor() as cur:
        # Ensure target table & PK exist (safe if already there)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS public.fish_transgene_alleles(
          fish_id               uuid NOT NULL REFERENCES public.fish(id) ON DELETE CASCADE,
          transgene_base_code   text NOT NULL,
          allele_number         text,
          zygosity              text,
          PRIMARY KEY (fish_id, transgene_base_code, allele_number)
        );
        """)

        # Stage the CSV (accept headers: fish_code, transgene_base_code, allele_number, zygosity)
        cur.execute("DROP TABLE IF EXISTS _stag_fta;")
        cur.execute("""
          CREATE TEMP TABLE _stag_fta(
            fish_code            text,
            transgene_base_code  text,
            allele_number        text,
            zygosity             text
          );
        """)
        with open(csv_path, newline='', encoding='utf-8') as f:
            r = csv.DictReader(f)
            with cur.copy("COPY _stag_fta (fish_code, transgene_base_code, allele_number, zygosity) FROM STDIN") as cp:
                for row in r:
                    cp.write_row([
                        (row.get("fish_code") or "").strip(),
                        (row.get("transgene_base_code") or "").strip(),
                        (row.get("allele_number") or "").strip(),
                        (row.get("zygosity") or "").strip(),
                    ])

        # Insert, resolving fish_code -> fish.id
        cur.execute("""
        INSERT INTO public.fish_transgene_alleles (fish_id, transgene_base_code, allele_number, zygosity)
        SELECT f.id,
               s.transgene_base_code,
               NULLIF(s.allele_number,'') AS allele_number,
               NULLIF(s.zygosity,'')
        FROM _stag_fta s
        JOIN public.fish f
          ON lower(trim(f.name)) = lower(trim(s.fish_code))
        WHERE COALESCE(s.fish_code,'') <> '' AND COALESCE(s.transgene_base_code,'') <> ''
        ON CONFLICT DO NOTHING;
        """)

        # QA
        cur.execute("SELECT 'fish_transgene_alleles', count(*) FROM public.fish_transgene_alleles;")
        print("|".join(map(str, cur.fetchone())))
        conn.commit()

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: seedkit_link_alleles.py /path/to/seedkit", file=sys.stderr)
        sys.exit(2)
    link_alleles(Path(sys.argv[1]))
