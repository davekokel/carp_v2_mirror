from __future__ import annotations

import os
import re
from typing import Dict, List, Set

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


def get_engine() -> Engine:
    url = os.environ.get("DB_URL")
    if not url:
        raise SystemExit("DB_URL must be set")
    print(f"DB_URL={url}")
    return create_engine(url)


def split_basecodes(geno_basecodes: str | None) -> List[str]:
    """
    Split genotype_basecodes into individual tokens.

    Supports:
      • v11 style: 'a||b'
      • legacy slug style: 'a|b'
      • legacy CSV style: 'a,b' or 'a,b|c'

    We normalize '||' to '|' and then split on both '|' and ','.
    """
    if not geno_basecodes:
        return []
    s = str(geno_basecodes).strip()
    if not s:
        return []
    s = s.replace("||", "|")
    tokens = re.split(r"[|,]", s)
    parts = [p.strip() for p in tokens]
    return [p for p in parts if p]


def _construct_key_variants(raw: str | None) -> Set[str]:
    """
    Generate a set of key variants for matching construct/base codes.

    Mirrors the normalization logic from v10_load_treatments_from_csv.py so that
    'MGCO-04', 'mgco004', 'mgco-4' etc. all map to the same construct.
    """
    s = (raw or "").strip()
    if not s:
        return set()

    keys: Set[str] = set()
    keys.add(s)
    keys.add(s.lower())

    m = re.match(r"^([A-Za-z]+)[-_]?(0*)(\d+)$", s)
    if not m:
        return keys

    prefix = m.group(1)
    digits = m.group(3)

    try:
        num = int(digits)
    except ValueError:
        return keys

    short = f"{prefix}-{num}"
    padded3 = f"{prefix}-{num:03d}"

    for v in (short, padded3):
        keys.add(v)
        keys.add(v.lower())

    return keys


def main() -> None:
    eng = get_engine()

    # Load genotypes_v11 (genotype_basecodes) and constructs (construct_code + base_code)
    with eng.begin() as cx:
        df_geno = pd.read_sql(
            text(
                """
                SELECT id::uuid AS genotype_id,
                       genotype_code,
                       genotype_basecodes
                FROM public.genotypes_v11
                """
            ),
            cx,
        )
        df_con = pd.read_sql(
            text(
                """
                SELECT id::uuid AS construct_id,
                       construct_code,
                       base_code
                FROM public.constructs
                """
            ),
            cx,
        )

    # Build a lookup from normalized key -> list of construct_ids
    key_to_constructs: Dict[str, List[str]] = {}
    for _, row in df_con.iterrows():
        construct_id = str(row["construct_id"])
        construct_code = (row.get("construct_code") or "").strip()
        base_code = (row.get("base_code") or "").strip()

        keys: Set[str] = set()
        for raw in (construct_code, base_code):
            keys.update(_construct_key_variants(raw))

        for k in keys:
            if not k:
                continue
            key_to_constructs.setdefault(k, []).append(construct_id)

    rows: List[Dict[str, str]] = []
    for _, row in df_geno.iterrows():
        gid = str(row["genotype_id"])
        basecodes = split_basecodes(row["genotype_basecodes"])
        for b in basecodes:
            for k in _construct_key_variants(b):
                for cid in key_to_constructs.get(k, []):
                    rows.append({"genotype_id": gid, "construct_id": cid})

    if not rows:
        print("[WARN] No genotype→construct links found from genotype_basecodes.")
        return

    df_rows = (
        pd.DataFrame(rows)
        .drop_duplicates(subset=["genotype_id", "construct_id"])
    )

    print(f"[INFO] Seeding join_genotype_constructs_v11 with {len(df_rows)} row(s).")

    with eng.begin() as cx:
        for r in df_rows.itertuples(index=False):
            cx.execute(
                text(
                    """
                    INSERT INTO public.join_genotype_constructs_v11 (genotype_id, construct_id)
                    VALUES (:gid, :cid)
                    ON CONFLICT (genotype_id, construct_id) DO NOTHING;
                    """
                ),
                {"gid": r.genotype_id, "cid": r.construct_id},
            )

    print("[OK] join_genotype_constructs_v11 seeding complete.")


if __name__ == "__main__":
    main()
