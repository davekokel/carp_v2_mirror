#!/usr/bin/env python
from __future__ import annotations

import os
import csv
import uuid
from pathlib import Path
from typing import Dict, List

import psycopg2


ROOT = Path(__file__).resolve().parents[1]

CONSTRUCTS_PATH = ROOT / "seed_kits" / "2025-11-15-121231-autoload" / "constructs_plasmid.csv"


def get_conn():
    dsn = os.getenv("DB_URL")
    if not dsn:
        raise RuntimeError("DB_URL env var is not set")
    return psycopg2.connect(dsn)


def get_table_columns(cur, table: str) -> List[str]:
    cur.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = %s
        ORDER BY ordinal_position
        """,
        (table,),
    )
    return [r[0] for r in cur.fetchall()]


def choose_code_col(cols: List[str], candidates: List[str]) -> str | None:
    for c in candidates:
        if c in cols:
            return c
    return None


def load_constructs(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"constructs_plasmid.csv not found at {path}")
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def ensure_fluor(cur, fluor_code: str) -> str | None:
    if not fluor_code:
        return None
    fluor_code = fluor_code.strip()
    if not fluor_code:
        return None
    cur.execute("SELECT id FROM public.fluors WHERE fluor_code = %s", (fluor_code,))
    row = cur.fetchone()
    if row:
        return row[0]
    new_id = str(uuid.uuid4())
    cur.execute(
        """
        INSERT INTO public.fluors (id, fluor_code, fluor_name)
        VALUES (%s, %s, %s)
        """,
        (new_id, fluor_code, fluor_code),
    )
    return new_id


def ensure_tag(cur, tag_code: str) -> str | None:
    if not tag_code:
        return None
    tag_code = tag_code.strip()
    if not tag_code:
        return None
    cur.execute("SELECT id FROM public.tags WHERE tag_code = %s", (tag_code,))
    row = cur.fetchone()
    if row:
        return row[0]
    new_id = str(uuid.uuid4())
    cur.execute(
        """
        INSERT INTO public.tags (id, tag_code, tag_name)
        VALUES (%s, %s, %s)
        """,
        (new_id, tag_code, tag_code),
    )
    return new_id


def ensure_fusion(cur, fluor_id: str | None, tag_id: str | None, tag_pos: str | None) -> str:
    # If there is already a fusion with these components, reuse it
    cur.execute(
        """
        SELECT id
        FROM public.fusions
        WHERE COALESCE(fluor_id::text,'') = COALESCE(%s,'')
          AND COALESCE(tag_id::text,'')   = COALESCE(%s,'')
          AND COALESCE(tag_pos,'')        = COALESCE(%s,'')
        """,
        (fluor_id, tag_id, tag_pos or None),
    )
    row = cur.fetchone()
    if row:
        return row[0]
    new_id = str(uuid.uuid4())
    cur.execute(
        """
        INSERT INTO public.fusions (id, fluor_id, tag_id, tag_pos)
        VALUES (%s, %s, %s, %s)
        """,
        (new_id, fluor_id, tag_id, tag_pos or None),
    )
    return new_id


def ensure_plasmid(cur, plasmids_cols: List[str], base_col: str, row: Dict[str, str]) -> str:
    base_code = (row.get("plasmid_code") or "").strip()
    if not base_code:
        raise ValueError("construct row missing plasmid_code")

    has_code_col = "code" in plasmids_cols

    # 1) If there's a row with code = base_code, reuse it
    if has_code_col:
        cur.execute(
            "SELECT id, {base_col} FROM public.plasmids WHERE code = %s".format(base_col=base_col),
            (base_code,),
        )
        found = cur.fetchone()
        if found:
            plasmid_id, existing_base = found
            # Optionally backfill base_col if it's NULL
            if existing_base is None:
                cur.execute(
                    f"UPDATE public.plasmids SET {base_col} = %s WHERE id = %s",
                    (base_code, plasmid_id),
                )
            return plasmid_id

    # 2) If there's a row with base_col = base_code, reuse it
    cur.execute(
        f"SELECT id FROM public.plasmids WHERE {base_col} = %s",
        (base_code,),
    )
    found = cur.fetchone()
    if found:
        plasmid_id = found[0]
        # Optionally backfill code if it's NULL and we have a code column
        if has_code_col:
            cur.execute(
                "UPDATE public.plasmids SET code = COALESCE(code, %s) WHERE id = %s",
                (base_code, plasmid_id),
            )
        return plasmid_id

    # 3) Otherwise, create a new plasmid row
    new_id = str(uuid.uuid4())
    cols = ["id", base_col]
    vals = [new_id, base_code]

    if has_code_col:
        cols.append("code")
        vals.append(base_code)

    # Try to set a human-friendly name if possible
    name_col = None
    for c in ("name", "plasmid_name", "display_name"):
        if c in plasmids_cols:
            name_col = c
            break
    if name_col:
        cols.append(name_col)
        vals.append((row.get("plasmid_name") or "").strip() or base_code)

    # Optional notes
    notes_col = None
    for c in ("notes", "plasmid_notes"):
        if c in plasmids_cols:
            notes_col = c
            break
    if notes_col:
        cols.append(notes_col)
        vals.append((row.get("plasmid_notes") or "").strip() or None)

    placeholders = ",".join(["%s"] * len(cols))
    cur.execute(
        f"INSERT INTO public.plasmids ({','.join(cols)}) VALUES ({placeholders})",
        vals,
    )
    return new_id


def ensure_join_plasmid_fusion(cur, plasmid_id: str, fusion_id: str):
    cur.execute(
        """
        SELECT 1
        FROM public.join_plasmid_fusions
        WHERE plasmid_id = %s AND fusion_id = %s
        """,
        (plasmid_id, fusion_id),
    )
    if cur.fetchone():
        return
    cur.execute(
        """
        INSERT INTO public.join_plasmid_fusions (plasmid_id, fusion_id)
        VALUES (%s, %s)
        """,
        (plasmid_id, fusion_id),
    )


def main() -> None:
    constructs = load_constructs(CONSTRUCTS_PATH)
    conn = get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                plasmids_cols = get_table_columns(cur, "plasmids")
                base_col = choose_code_col(plasmids_cols, ["plasmid_base_code", "base_code", "code"])
                if not base_col:
                    raise RuntimeError("Could not find a base code column on public.plasmids")

                print(f"[INFO] Using {base_col} as plasmid base code column.")

                n_plasmids = 0
                n_fusions = 0
                n_links = 0

                for row in constructs:
                    base_code = (row.get("plasmid_code") or "").strip()
                    if not base_code:
                        continue

                    plasmid_id = ensure_plasmid(cur, plasmids_cols, base_col, row)
                    n_plasmids += 1

                    fluor_code = (row.get("fluor_code") or "").strip()
                    tag_code = (row.get("tag_code") or "").strip()
                    tag_pos = (row.get("tag_pos") or "").strip() or None

                    # If no fluor/tag info, skip fusions
                    if not fluor_code and not tag_code:
                        continue

                    fluor_id = ensure_fluor(cur, fluor_code) if fluor_code else None
                    tag_id = ensure_tag(cur, tag_code) if tag_code else None
                    fusion_id = ensure_fusion(cur, fluor_id, tag_id, tag_pos)
                    n_fusions += 1

                    ensure_join_plasmid_fusion(cur, plasmid_id, fusion_id)
                    n_links += 1

        print(f"[OK] Processed {n_plasmids} plasmid rows, {n_fusions} fusion rows, {n_links} links.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
