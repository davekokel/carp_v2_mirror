#!/usr/bin/env python3
import os, sys, csv
from pathlib import Path
import psycopg

CONN = os.environ.get("CONN")
if not CONN:
    print("ERROR: Set CONN env var", file=sys.stderr); sys.exit(1)

def ensure_schema(cur):
    cur.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS public.treatments(
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          performed_at date,
          treatment_type text,
          material_code text,
          method text,
          operator text,
          notes text
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS public.fish_treatments(
          fish_id uuid REFERENCES public.fish(id) ON DELETE CASCADE,
          treatment_id uuid REFERENCES public.treatments(id) ON DELETE CASCADE,
          PRIMARY KEY (fish_id, treatment_id)
        )
    """)

def load_treatments(kit_dir: Path):
    # Prefer unified file; if missing, try the split ones and normalize
    unified = kit_dir / "05_treatments_unified.csv"
    split_p = kit_dir / "05_treatments.csv"
    split_r = kit_dir / "05b_rna_treatments.csv"
    split_d = kit_dir / "05c_dye_treatments.csv"

    records = []

    def add_unified_rows(path: Path):
        with open(path, newline='', encoding='utf-8') as f:
            r = csv.DictReader(f)
            for row in r:
                records.append({
                    "fish_code": (row.get("fish_code") or "").strip(),
                    "treatment_date": (row.get("treatment_date") or "").strip(),
                    "treatment_type": (row.get("treatment_type") or "").strip(),
                    "material_code": (row.get("material_code") or "").strip(),
                    "method": (row.get("method") or "").strip(),
                    "operator": (row.get("operator") or "").strip(),
                    "notes": (row.get("notes") or "").strip(),
                })

    def add_split_rows(path: Path, kind: str, code_field: str):
        if not path.exists(): return
        with open(path, newline='', encoding='utf-8') as f:
            r = csv.DictReader(f)
            for row in r:
                records.append({
                    "fish_code": (row.get("fish_code") or "").strip(),
                    "treatment_date": (row.get("treatment_date") or "").strip(),
                    "treatment_type": kind,
                    "material_code": (row.get(code_field) or "").strip(),
                    "method": (row.get("method") or "").strip(),
                    "operator": (row.get("operator") or "").strip(),
                    "notes": (row.get("notes") or "").strip(),
                })

    if unified.exists():
        print(f">> Loading unified treatments from: {unified}")
        add_unified_rows(unified)
    else:
        if split_p.exists():
            print(f">> Loading plasmid treatments from: {split_p}")
            add_split_rows(split_p, "plasmid", "plasmid_code")
        if split_r.exists():
            print(f">> Loading RNA treatments from: {split_r}")
            add_split_rows(split_r, "rna", "rna_code")
        if split_d.exists():
            print(f">> Loading dye treatments from: {split_d}")
            add_split_rows(split_d, "dye", "dye_code")

    if not records:
        print("-- No treatments found; skipping.")
        return

    with psycopg.connect(CONN) as conn, conn.cursor() as cur:
        ensure_schema(cur)

        # Stage
        cur.execute("DROP TABLE IF EXISTS _stag_tx")
        cur.execute("""
            CREATE TEMP TABLE _stag_tx(
              fish_code text,
              treatment_date_txt text,
              treatment_type text,
              material_code text,
              method text,
              operator text,
              notes text
            )
        """)
        with cur.copy("COPY _stag_tx (fish_code, treatment_date_txt, treatment_type, material_code, method, operator, notes) FROM STDIN") as cp:
            for r in records:
                cp.write_row([
                    r["fish_code"], r["treatment_date"], r["treatment_type"],
                    r["material_code"], r["method"], r["operator"], r["notes"]
                ])

        # Insert treatments; link to fish
        cur.execute("""
            WITH ins AS (
              INSERT INTO public.treatments(performed_at, treatment_type, material_code, method, operator, notes)
              SELECT NULLIF(trim(treatment_date_txt),'')::date,
                     NULLIF(trim(treatment_type),''),
                     NULLIF(trim(material_code),''),
                     NULLIF(trim(method),''),
                     NULLIF(trim(operator),''),
                     NULLIF(trim(notes),'')
              FROM _stag_tx
              RETURNING id, performed_at, treatment_type, material_code, method, operator, notes
            )
            INSERT INTO public.fish_treatments(fish_id, treatment_id)
            SELECT f.id, i.id
            FROM _stag_tx s
            JOIN ins i
              ON i.performed_at IS NOT DISTINCT FROM NULLIF(trim(s.treatment_date_txt),'')::date
             AND i.treatment_type IS NOT DISTINCT FROM NULLIF(trim(s.treatment_type),'')
             AND i.material_code  IS NOT DISTINCT FROM NULLIF(trim(s.material_code),'')
             AND i.method         IS NOT DISTINCT FROM NULLIF(trim(s.method),'')
             AND i.operator       IS NOT DISTINCT FROM NULLIF(trim(s.operator),'')
             AND i.notes          IS NOT DISTINCT FROM NULLIF(trim(s.notes),'')
            JOIN public.fish f ON lower(trim(f.name)) = lower(trim(s.fish_code))
            ON CONFLICT DO NOTHING
        """)

        # Report
        cur.execute("SELECT 'treatments', COUNT(*) FROM public.treatments")
        print("|".join(map(str, cur.fetchone())))
        conn.commit()

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: seedkit_load_treatments.py /path/to/seedkit", file=sys.stderr); sys.exit(2)
    load_treatments(Path(sys.argv[1]))
