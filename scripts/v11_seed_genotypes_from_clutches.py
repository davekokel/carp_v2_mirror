#!/usr/bin/env python3
# v11_seed_genotypes_from_clutches.py

from __future__ import annotations
import sys, pathlib, hashlib, json, os
import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

# repo boot
ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from carp_app.ui.lib.app_ctx import get_engine


def stable_hash(text_in: str) -> str:
    """
    Deterministic genotype code generator:
    SHA-256(text_in) → first 10 hex chars → upper-case.
    """
    h = hashlib.sha256(text_in.encode("utf-8")).hexdigest()
    return h[:10].upper()


def normalize_basecodes(geno_str: str | None) -> str | None:
    """
    Extract PDQM-xxx or MGCO-xxx basecodes from the pretty string.
    Example: "Tg(PDQM-034)gu18 × Tg(PDQM-034)gu19" → "PDQM-034||PDQM-034"
    """
    if not geno_str:
        return None

    import re
    hits = re.findall(r'Tg\(([A-Z0-9\-]+)\)gu[0-9]+', geno_str)
    if not hits:
        return None

    return "||".join(hits)


def main() -> None:
    db_url = os.getenv("DB_URL")
    if not db_url:
        print("ERROR: DB_URL is not set")
        sys.exit(1)

    eng: Engine = get_engine()

    # 1. Pull all clutches with any genotype string
    sql = text("""
        SELECT id, clutch_code, genotype_base_codes, genotype_pretty
        FROM public.clutches
        ORDER BY clutch_code;
    """)

    with eng.begin() as cx:
        df = pd.read_sql(sql, cx)

    # 2. Build canonical genotype definitions
    rows_to_insert = []
    clutch_updates = []

    for r in df.itertuples(index=False):
        geno_pretty = (r.genotype_pretty or r.genotype_base_codes or "").strip()
        if not geno_pretty:
            # no genotype at all
            clutch_updates.append((r.id, None))
            continue

        basecodes = normalize_basecodes(geno_pretty) or ""
        code_src = json.dumps({
            "pretty": geno_pretty,
            "basecodes": basecodes
        }, sort_keys=True)

        gcode = "G-" + stable_hash(code_src)

        rows_to_insert.append((gcode, geno_pretty, basecodes, r.id))

    # 3. Deduplicate by genotype_code
    df_insert = (
        pd.DataFrame(rows_to_insert,
                     columns=["genotype_code","genotype_pretty","genotype_basecodes","clutch_id"])
        .drop_duplicates(subset=["genotype_code"])
    )

    # 4. Insert into genotypes_v11 if missing
    with eng.begin() as cx:
        for row in df_insert.itertuples(index=False):
            cx.execute(text("""
                INSERT INTO public.genotypes_v11 (genotype_code, genotype_pretty, genotype_basecodes)
                VALUES (:code, :pretty, :basecodes)
                ON CONFLICT (genotype_code) DO NOTHING;
            """), {
                "code": row.genotype_code,
                "pretty": row.genotype_pretty,
                "basecodes": row.genotype_basecodes
            })

    # 5. Refetch mapping to assign genotype_v11_id to clutches
    with eng.begin() as cx:
        gmap = pd.read_sql(text("""
            SELECT id, genotype_code
            FROM public.genotypes_v11;
        """), cx)

    code_to_id = dict(zip(gmap.genotype_code, gmap.id))

    updates = []
    for r in rows_to_insert:
        gcode = r[0]
        clutch_id = r[3]
        gid = code_to_id.get(gcode)
        updates.append((gid, clutch_id))

    with eng.begin() as cx:
        for gid, cid in updates:
            cx.execute(text("""
                UPDATE public.clutches
                SET genotype_v11_id = :gid
                WHERE id = :cid;
            """), {"gid": gid, "cid": cid})

    print(f"[OK] seeded genotypes_v11: upserted {len(df_insert)} definitions; assigned {len(updates)} clutches.")


if __name__ == "__main__":
    main()
