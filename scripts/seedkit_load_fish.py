#!/usr/bin/env python3
import os, sys, csv
from pathlib import Path
import psycopg

CONN = os.environ.get("CONN")
if not CONN:
    print("ERROR: Set CONN env var (e.g. postgres://…)", file=sys.stderr)
    sys.exit(1)

CSV_NAME = "01_fish.csv"

def upsert_fish(kit_dir: Path):
    csv_path = kit_dir / CSV_NAME
    if not csv_path.exists():
        print(f"ERROR: file not found: {csv_path}", file=sys.stderr)
        sys.exit(1)

    batch = kit_dir.name
    print(f">> Upserting fish (batch={batch}) from: {csv_path}")

    # Read once to learn which columns exist and collect rows
    with open(csv_path, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        fieldnames = [c.strip() for c in (r.fieldnames or [])]
        rows = [ {k.strip(): (v or "").strip() for k, v in row.items()} for row in r ]

    # Map legacy headers to our schema (support both old and new)
    # CSV must have "fish_code" (or "name") as the human fish name.
    def get_col(name: str, *aliases: str):
        candidates = [name, *aliases]
        for c in candidates:
            if c in fieldnames:
                return c
        return None

    col_fish_name   = get_col("fish_code", "name")  # human fish name
    col_dob         = get_col("date_of_birth", "dob")
    col_stage       = get_col("line_building_stage", "stage")
    col_nickname    = get_col("nickname")
    col_strain      = get_col("strain")
    col_description = get_col("description", "notes")

    if not col_fish_name:
        print("ERROR: CSV must include 'fish_code' (or legacy 'name')", file=sys.stderr)
        sys.exit(2)

    # Build a normalized list of tuples for COPY into a temp staging table.
    # All as text; we’ll cast the date safely in SQL.
    staged = []
    for row in rows:
        name        = row.get(col_fish_name, "")
        dob         = row.get(col_dob, "") if col_dob else ""
        stage       = row.get(col_stage, "") if col_stage else ""
        nickname    = row.get(col_nickname, "") if col_nickname else ""
        strain      = row.get(col_strain, "") if col_strain else ""
        description = row.get(col_description, "") if col_description else ""
        if name.strip() == "":
            continue
        staged.append((name, dob, stage, nickname, strain, description))

    with psycopg.connect(CONN) as conn, conn.cursor() as cur:
        # Ensure columns / indexes exist (safe if already there)
        cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_fish_name ON public.fish(name)")
        cur.execute("""
            ALTER TABLE public.fish
              ADD COLUMN IF NOT EXISTS date_of_birth date,
              ADD COLUMN IF NOT EXISTS line_building_stage text,
              ADD COLUMN IF NOT EXISTS nickname text,
              ADD COLUMN IF NOT EXISTS strain text,
              ADD COLUMN IF NOT EXISTS description text,
              ADD COLUMN IF NOT EXISTS batch_label text;
        """)

        # Stage
        cur.execute("DROP TABLE IF EXISTS _stag_fish")
        cur.execute("""
            CREATE TEMP TABLE _stag_fish(
              name text,
              date_of_birth text,
              line_building_stage text,
              nickname text,
              strain text,
              description text
            ) ON COMMIT DROP
        """)
        if staged:
            with cur.copy("COPY _stag_fish (name, date_of_birth, line_building_stage, nickname, strain, description) FROM STDIN") as cp:
                for rec in staged:
                    cp.write_row(rec)

        # Upsert:
        # - Insert new fish with batch_label
        # - Update existing fields only when CSV provides a non-empty value
        cur.execute("""
            -- Insert any new fish names
            INSERT INTO public.fish(name, batch_label)
            SELECT DISTINCT trim(name), %s
            FROM _stag_fish
            WHERE COALESCE(trim(name),'') <> ''
            ON CONFLICT (name) DO NOTHING
        """, (batch,))

        # Update existing rows (and also set/update batch_label for these)
        cur.execute(f"""
            UPDATE public.fish AS f
            SET
              batch_label         = %s,
              date_of_birth       = COALESCE(NULLIF(s.date_of_birth,'')::date, f.date_of_birth),
              line_building_stage = COALESCE(NULLIF(s.line_building_stage,''), f.line_building_stage),
              nickname            = COALESCE(NULLIF(s.nickname,''), f.nickname),
              strain              = COALESCE(NULLIF(s.strain,''), f.strain),
              description         = COALESCE(NULLIF(s.description,''), f.description)
            FROM _stag_fish s
            WHERE trim(s.name) = f.name
        """, (batch,))

        # Report
        cur.execute("""
            SELECT %s AS batch, COUNT(*) AS fish_in_batch
            FROM public.fish
            WHERE batch_label = %s
        """, (batch, batch))
        print("|".join(map(str, cur.fetchone())))

        conn.commit()

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: seedkit_load_fish.py /path/to/seedkit_folder", file=sys.stderr)
        sys.exit(2)
    upsert_fish(Path(sys.argv[1]))