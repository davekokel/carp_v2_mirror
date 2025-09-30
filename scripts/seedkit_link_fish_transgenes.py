#!/usr/bin/env python3
import sys, csv, argparse
from pathlib import Path
from seedkit_util import get_conn

def run(kit: Path):
    candidates = [
        kit / "10_fish_transgene_alleles.csv",
        kit / "fish_transgene_alleles.csv",
    ]
    csv_path = next((p for p in candidates if p.exists()), None)
    if not csv_path:
        print(f"-- No fish↔transgene link CSV in: {kit}")
        return

    print(f">> Linking fish ↔ transgenes from: {csv_path}")

    with get_conn() as conn, conn.cursor() as cur, open(csv_path, newline='', encoding='utf-8') as f:
        # Ensure link table + indexes exist
        cur.execute("""
            CREATE TABLE IF NOT EXISTS public.fish_transgenes(
              fish_id        uuid NOT NULL REFERENCES public.fish(id) ON DELETE CASCADE,
              transgene_code text NOT NULL REFERENCES public.transgenes(code) ON DELETE RESTRICT,
              PRIMARY KEY(fish_id, transgene_code)
            );
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS ix_fish_transgenes_fish ON public.fish_transgenes(fish_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_fish_transgenes_tg   ON public.fish_transgenes(transgene_code);")

        # Stage just the two columns we need
        cur.execute("DROP TABLE IF EXISTS _stag_fish_tg;")
        cur.execute("""
            CREATE TEMP TABLE _stag_fish_tg(
              fish_code            text,
              transgene_base_code  text
            );
        """)
        rdr = csv.DictReader(f)
        with cur.copy("COPY _stag_fish_tg (fish_code, transgene_base_code) FROM STDIN") as cp:
            for row in rdr:
                cp.write_row([
                    (row.get('fish_code') or '').strip(),
                    (row.get('transgene_base_code') or '').strip()
                ])

        # Insert links: fish_code -> fish.name ; base_code -> transgenes.transgene_base_code -> code
        cur.execute("""
            INSERT INTO public.fish_transgenes(fish_id, transgene_code)
            SELECT f.id, tg.code
            FROM _stag_fish_tg s
            JOIN public.fish f
              ON lower(trim(f.name)) = lower(trim(s.fish_code))
            JOIN public.transgenes tg
              ON tg.transgene_base_code = trim(s.transgene_base_code)
            WHERE COALESCE(s.fish_code,'') <> '' AND COALESCE(s.transgene_base_code,'') <> ''
            ON CONFLICT DO NOTHING;
        """)

        cur.execute("SELECT 'fish_transgenes', COUNT(*) FROM public.fish_transgenes;")
        print("|".join(map(str, cur.fetchone())))

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Link fish ↔ transgenes from a kit")
    ap.add_argument("kit", type=Path)
    args = ap.parse_args()
    run(args.kit)
