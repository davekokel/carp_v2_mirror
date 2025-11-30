from __future__ import annotations

import os
from typing import Dict, List

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
    if not geno_basecodes:
        return []
    parts = [p.strip() for p in str(geno_basecodes).split("||")]
    return [p for p in parts if p]


def main() -> None:
    eng = get_engine()

    # Load genotypes_v11 (genotype_basecodes) and constructs (base_code)
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
                       base_code
                FROM public.constructs
                """
            ),
            cx,
        )

    basecode_to_constructs: Dict[str, List[str]] = {}
    for _, row in df_con.iterrows():
        base = (row["base_code"] or "").strip()
        if not base:
            continue
        basecode_to_constructs.setdefault(base, []).append(str(row["construct_id"]))

    rows = []
    for _, row in df_geno.iterrows():
        gid = str(row["genotype_id"])
        basecodes = split_basecodes(row["genotype_basecodes"])
        for b in basecodes:
            for cid in basecode_to_constructs.get(b, []):
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
