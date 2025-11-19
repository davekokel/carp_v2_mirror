#!/usr/bin/env python
from __future__ import annotations

import argparse
import os
import uuid
import csv
from pathlib import Path
from typing import Dict, List, Tuple

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


def list_tables(cur) -> List[str]:
    cur.execute(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
        """
    )
    return [r[0] for r in cur.fetchall()]


def _choose_code_col(cols: List[str], candidates: List[str]) -> str | None:
    for c in candidates:
        if c in cols:
            return c
    return None


# ----------------- CLUTCHES -----------------


def load_clutches(cur, clutches_rows: List[Dict[str, str]]) -> Dict[str, str]:
    """
    Insert imaging clutches into public.clutches, return clutch_code -> clutch_id (as string).
    """
    cols = get_table_columns(cur, "clutches")
    has_notes = "notes" in cols

    clutch_map: Dict[str, str] = {}

    for row in clutches_rows:
        code = (row.get("clutch_code") or "").strip()
        if not code:
            continue

        cur.execute(
            "SELECT id FROM public.clutches WHERE clutch_code = %s",
            (code,),
        )
        existing = cur.fetchone()
        if existing:
            clutch_map[code] = str(existing[0])
            continue

        new_id = str(uuid.uuid4())
        clutch_date = row.get("clutch_date") or None
        est_eggs = row.get("estimated_egg_count") or None
        est_eggs_val = int(est_eggs) if est_eggs not in (None, "", "NaN") else None

        insert_cols = ["id", "clutch_date", "clutch_code", "estimated_egg_count"]
        values = [new_id, clutch_date, code, est_eggs_val]

        if has_notes:
            note_parts = [row.get("notes", "").strip()]
            g_label = row.get("genotype_cross_label") or ""
            if g_label:
                note_parts.append(f"genotype_cross_label={g_label}")
            t_pl = row.get("treatment_plasmids_text") or ""
            t_rna = row.get("treatment_rnas_text") or ""
            t_dye = row.get("treatment_dyes_text") or ""
            if any([t_pl, t_rna, t_dye]):
                note_parts.append(
                    f"treatments(plasmids={t_pl}; rnas={t_rna}; dyes={t_dye})"
                )
            note_val = " | ".join(p for p in note_parts if p)
            insert_cols.append("notes")
            values.append(note_val or None)

        placeholders = ",".join(["%s"] * len(insert_cols))
        cur.execute(
            f"""
            INSERT INTO public.clutches ({",".join(insert_cols)})
            VALUES ({placeholders})
            """,
            values,
        )
        clutch_map[code] = new_id

    return clutch_map


# ----------------- TREATMENTS -----------------


def get_plasmid_rna_dye_maps(cur) -> Tuple[Dict[str, str], Dict[str, str], Dict[str, str]]:
    """
    Build base_code -> id (as string) maps from DB for plasmids, rnas, dyes.
    We dynamically choose code columns based on what's actually present.
    """
    plasmids: Dict[str, str] = {}
    rnas: Dict[str, str] = {}
    dyes: Dict[str, str] = {}

    tables = set(list_tables(cur))

    if "plasmids" in tables:
        pl_cols = get_table_columns(cur, "plasmids")
        pl_code_col = _choose_code_col(pl_cols, ["plasmid_base_code", "base_code", "code"])
        if pl_code_col:
            cur.execute(
                f"""
                SELECT id, {pl_code_col}
                FROM public.plasmids
                WHERE {pl_code_col} IS NOT NULL
                """
            )
            for pid, base in cur.fetchall():
                if base:
                    plasmids[str(base)] = str(pid)

    if "rnas" in tables:
        rna_cols = get_table_columns(cur, "rnas")
        rna_code_col = _choose_code_col(rna_cols, ["rna_base_code", "base_code", "code"])
        if rna_code_col:
            cur.execute(
                f"""
                SELECT id, {rna_code_col}
                FROM public.rnas
                WHERE {rna_code_col} IS NOT NULL
                """
            )
            for rid, base in cur.fetchall():
                if base:
                    rnas[str(base)] = str(rid)

    if "dyes" in tables:
        dye_cols = get_table_columns(cur, "dyes")
        dye_code_col = _choose_code_col(dye_cols, ["dye_base_code", "base_code", "code"])
        if dye_code_col:
            cur.execute(
                f"""
                SELECT id, {dye_code_col}
                FROM public.dyes
                WHERE {dye_code_col} IS NOT NULL
                """
            )
            for did, base in cur.fetchall():
                if base:
                    dyes[str(base)] = str(did)

    return plasmids, rnas, dyes


def load_treatments(
    cur,
    treatments_rows: List[Dict[str, str]],
) -> Dict[str, str]:
    """
    Insert imaging treatments into public.treatments and return treat_code -> id (as string).
    """
    cols = get_table_columns(cur, "treatments")
    has_treat_text = "treat_text" in cols
    has_kind_code = "kind_code" in cols
    has_notes = "notes" in cols

    treatment_map: Dict[str, str] = {}

    for row in treatments_rows:
        code = (row.get("treatment_code") or "").strip()
        if not code:
            continue

        cur.execute(
            "SELECT id FROM public.treatments WHERE treat_code = %s",
            (code,),
        )
        existing = cur.fetchone()
        if existing:
            treatment_map[code] = str(existing[0])
            continue

        new_id = str(uuid.uuid4())

        insert_cols = ["id", "treat_code"]
        values = [new_id, code]

        if has_treat_text:
            txt = row.get("plasmid_tokens_raw") or row.get("rna_tokens_raw") or code
            insert_cols.append("treat_text")
            values.append(txt[:255])

        if has_kind_code:
            insert_cols.append("kind_code")
            values.append("IMAGING")

        if has_notes:
            desc_bits = []
            for key in [
                "plasmid_tokens_raw",
                "rna_tokens_raw",
                "protein_tokens_raw",
                "dye_tokens_raw",
                "unmapped_plasmid_tokens",
                "unmapped_rna_tokens",
            ]:
                val = row.get(key) or ""
                if val:
                    desc_bits.append(f"{key}={val}")
            insert_cols.append("notes")
            values.append(" | ".join(desc_bits) or None)

        placeholders = ",".join(["%s"] * len(insert_cols))
        cur.execute(
            f"""
            INSERT INTO public.treatments ({",".join(insert_cols)})
            VALUES ({placeholders})
            """,
            values,
        )
        treatment_map[code] = new_id

    return treatment_map


def load_join_treatment_components(
    cur,
    treatments_rows: List[Dict[str, str]],
    treatment_map: Dict[str, str],
    plasmid_map: Dict[str, str],
    rna_map: Dict[str, str],
    dye_map: Dict[str, str],
) -> None:
    """
    Insert rows into join_treatment_plasmids / join_treatment_rnas / join_treatment_dyes.
    """
    tables = set(list_tables(cur))

    jt_pl_cols = get_table_columns(cur, "join_treatment_plasmids") if "join_treatment_plasmids" in tables else []
    jt_rna_cols = get_table_columns(cur, "join_treatment_rnas") if "join_treatment_rnas" in tables else []
    jt_dye_cols = get_table_columns(cur, "join_treatment_dyes") if "join_treatment_dyes" in tables else []

    has_jt_pl = {"treatment_id", "plasmid_id"}.issubset(jt_pl_cols)
    has_jt_rna = {"treatment_id", "rna_id"}.issubset(jt_rna_cols)
    has_jt_dye = {"treatment_id", "dye_id"}.issubset(jt_dye_cols)

    jt_pl_has_id = "id" in jt_pl_cols
    jt_rna_has_id = "id" in jt_rna_cols
    jt_dye_has_id = "id" in jt_dye_cols

    for row in treatments_rows:
        code = (row.get("treatment_code") or "").strip()
        if not code:
            continue
        treatment_id = treatment_map.get(code)
        if not treatment_id:
            continue

        base_codes = (row.get("plasmid_base_codes") or "").split(",")
        base_codes = [b.strip() for b in base_codes if b.strip()]

        for base in base_codes:
            if has_jt_pl and base in plasmid_map:
                pid = plasmid_map[base]
                cur.execute(
                    """
                    SELECT 1 FROM public.join_treatment_plasmids
                    WHERE treatment_id = %s AND plasmid_id = %s
                    """,
                    (treatment_id, pid),
                )
                if not cur.fetchone():
                    if jt_pl_has_id:
                        cur.execute(
                            """
                            INSERT INTO public.join_treatment_plasmids (id, treatment_id, plasmid_id)
                            VALUES (%s, %s, %s)
                            """,
                            (str(uuid.uuid4()), treatment_id, pid),
                        )
                    else:
                        cur.execute(
                            """
                            INSERT INTO public.join_treatment_plasmids (treatment_id, plasmid_id)
                            VALUES (%s, %s)
                            """,
                            (treatment_id, pid),
                        )
            if has_jt_rna and base in rna_map:
                rid = rna_map[base]
                cur.execute(
                    """
                    SELECT 1 FROM public.join_treatment_rnas
                    WHERE treatment_id = %s AND rna_id = %s
                    """,
                    (treatment_id, rid),
                )
                if not cur.fetchone():
                    if jt_rna_has_id:
                        cur.execute(
                            """
                            INSERT INTO public.join_treatment_rnas (id, treatment_id, rna_id)
                            VALUES (%s, %s, %s)
                            """,
                            (str(uuid.uuid4()), treatment_id, rid),
                        )
                    else:
                        cur.execute(
                            """
                            INSERT INTO public.join_treatment_rnas (treatment_id, rna_id)
                            VALUES (%s, %s)
                            """,
                            (treatment_id, rid),
                        )
            if has_jt_dye and base in dye_map:
                did = dye_map[base]
                cur.execute(
                    """
                    SELECT 1 FROM public.join_treatment_dyes
                    WHERE treatment_id = %s AND dye_id = %s
                    """,
                    (treatment_id, did),
                )
                if not cur.fetchone():
                    if jt_dye_has_id:
                        cur.execute(
                            """
                            INSERT INTO public.join_treatment_dyes (id, treatment_id, dye_id)
                            VALUES (%s, %s, %s)
                            """,
                            (str(uuid.uuid4()), treatment_id, did),
                        )
                    else:
                        cur.execute(
                            """
                            INSERT INTO public.join_treatment_dyes (treatment_id, dye_id)
                            VALUES (%s, %s)
                            """,
                            (treatment_id, did),
                        )


def load_join_clutch_treatments(
    cur,
    clutch_treat_rows: List[Dict[str, str]],
    clutch_map: Dict[str, str],
    treatment_map: Dict[str, str],
) -> None:
    tables = set(list_tables(cur))
    if "join_clutch_treatments" not in tables:
        print("join_clutch_treatments table not found; skipping clutch-treatment links.")
        return

    jt_cols = get_table_columns(cur, "join_clutch_treatments")
    has_notes = "notes" in jt_cols
    has_id = "id" in jt_cols

    for row in clutch_treat_rows:
        code = (row.get("clutch_code") or "").strip()
        t_code = (row.get("treatment_code") or "").strip()
        if not code or not t_code:
            continue

        clutch_id = clutch_map.get(code)
        treatment_id = treatment_map.get(t_code)
        if not clutch_id or not treatment_id:
            continue

        cur.execute(
            """
            SELECT 1 FROM public.join_clutch_treatments
            WHERE clutch_id = %s AND treatment_id = %s
            """,
            (clutch_id, treatment_id),
        )
        if cur.fetchone():
            continue

        insert_cols = []
        values = []

        if has_id:
            insert_cols.append("id")
            values.append(str(uuid.uuid4()))

        insert_cols.extend(["clutch_id", "treatment_id"])
        values.extend([clutch_id, treatment_id])

        if has_notes:
            insert_cols.append("notes")
            values.append("imaging_backfill")

        placeholders = ",".join(["%s"] * len(insert_cols))
        cur.execute(
            f"""
            INSERT INTO public.join_clutch_treatments ({",".join(insert_cols)})
            VALUES ({placeholders})
            """,
            values,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Load imaging clutches and treatments into DB.")
    parser.add_argument(
        "--clutches-csv",
        type=Path,
        default=ROOT / "seed_kits" / "legacy_import" / "working" / "imaging_clutches_from_sheet_draft.csv",
        help="Path to imaging_clutches_from_sheet_draft.csv",
    )
    parser.add_argument(
        "--treatments-csv",
        type=Path,
        default=ROOT / "seed_kits" / "legacy_import" / "working" / "imaging_treatments_from_sheet_draft.csv",
        help="Path to imaging_treatments_from_sheet_draft.csv",
    )
    parser.add_argument(
        "--clutch-treatments-csv",
        type=Path,
        default=ROOT / "seed_kits" / "legacy_import" / "working" / "imaging_clutch_treatments_from_sheet_draft.csv",
        help="Path to imaging_clutch_treatments_from_sheet_draft.csv",
    )
    args = parser.parse_args()

    clutches_rows = read_csv(args.clutches_csv)
    treatments_rows = read_csv(args.treatments_csv)
    clutch_treat_rows = read_csv(args.clutch_treatments_csv)

    conn = get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                clutch_map = load_clutches(cur, clutches_rows)
                treatment_map = load_treatments(cur, treatments_rows)
                plasmid_map, rna_map, dye_map = get_plasmid_rna_dye_maps(cur)
                load_join_treatment_components(cur, treatments_rows, treatment_map, plasmid_map, rna_map, dye_map)
                load_join_clutch_treatments(cur, clutch_treat_rows, clutch_map, treatment_map)
        print("Done: imaging clutches, treatments, and clutch↔treatment links loaded.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
