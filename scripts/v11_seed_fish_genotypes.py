#!/usr/bin/env python3
from __future__ import annotations
import os
from pathlib import Path
import pandas as pd
from sqlalchemy import create_engine, text

def get_engine():
    url = os.environ.get("DB_URL")
    if not url:
        raise SystemExit("DB_URL is not set")
    return create_engine(url)

def main():
    engine = create_engine(os.environ['DB_URL'])

    with engine.begin() as cx:
        df = pd.read_sql(
            text(
                """
                SELECT
                  fis.fish_instance_id AS fish_id,
                  fis.fish_code,
                  fis.genotype_pretty,
                  fis.genotype_basecodes
                FROM public.v11_fish_instance_star AS fis
                WHERE fis.genotype_basecodes IS NOT NULL
                  AND fis.genotype_basecodes <> ''
                """
            ),
            cx,
        )

    if df.empty:
        print("[v11_seed_fish_genotypes] no fish with genotype_basecodes; nothing to do")
        return

    df = df.dropna(subset=["genotype_basecodes"]).copy()
    df["genotype_basecodes"] = df["genotype_basecodes"].astype(str).str.strip()
    df = df[df["genotype_basecodes"] != ""]
    if df.empty:
        print("[v11_seed_fish_genotypes] no non-empty genotype_basecodes; nothing to do")
        return

    uniq = df[["genotype_basecodes", "genotype_pretty"]].drop_duplicates()

    with engine.begin() as cx:
        for _, row in uniq.iterrows():
            basecodes = row["genotype_basecodes"]
            pretty = str(row.get("genotype_pretty") or "")
            if not basecodes:
                raise SystemExit(f"[v11_seed_fish_genotypes] empty genotype_basecodes for row {row.to_dict()}")
            res = cx.execute(
                text(
                    """
                    INSERT INTO public.genotypes_v11 (
                      id,
                      genotype_code,
                      genotype_pretty,
                      genotype_basecodes,
                      created_at
                    )
                    VALUES (
                      gen_random_uuid(),
                      'G-' || upper(encode(sha256(cast(:bc as bytea)), 'hex'))::text,
                      :pretty,
                      :bc,
                      now()
                    )
                    ON CONFLICT (genotype_code) DO NOTHING
                    RETURNING id
                    """
                ),
                {"bc": basecodes, "pretty": pretty},
            )
            row_id = res.scalar()
            if row_id is None:
                pass

    with engine.begin() as cx:
        df = pd.read_sql(
            text(
                """
                SELECT
                  fis.fish_instance_id AS fish_id,
                  fis.genotype_basecodes AS basecodes,
                  g.id AS genotype_id
                FROM public.v11_fish_instance_star fis
                JOIN public.genotypes_v11 g
                  ON g.genotype_basecodes = fis.genotype_basecodes
                """
            ),
            cx,
        )
        if df.empty:
            raise SystemExit("[v11_seed_fish_genotypes] no matching genotypes_v11 rows for fish genotype_basecodes; check data")
        updated = 0
        for _, row in df.iterrows():
            res = cx.execute(
                text(
                    """
                    UPDATE public.fish_instances_v10 AS fi
                    SET genotype_v11_id = :gid
                    WHERE fi.id = :fid AND (fi.genotype_v11_id IS NULL OR fi.genotype_v11_id <> :gid)
                    """
                ),
                {"gid": row["genotype_id"], "fid": row["fish_id"]},
            )
            updated += res.rowcount
        print(f"[v11_seed_fish_genotypes] assigned genotype_v11_id for {updated} fish instance(s).")

if __name__ == "__main__":
    main()
