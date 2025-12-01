#!/usr/bin/env python3
from __future__ import annotations
import os
import pandas as pd
from sqlalchemy import create_engine, text

def main() -> None:
    db_url = os.environ.get("DB_URL")
    if not db_url:
        raise SystemExit("DB_URL is not set")
    engine = create_engine(db_url)

    # 1) Pull fish + construct rollups from the star view
    with engine.begin() as cx:
        df = pd.read_sql(
            text(
                """
                SELECT
                  fis.fish_instance_id AS fish_id,
                  fis.fish_code,
                  fis.genotype_v11_id,
                  fis.genotype_basecodes
                FROM public.v11_fish_instance_star AS fis
                """
            ),
            cx,
        )

    # Only consider fish that actually have construct-based genotype_basecodes
    df = df.dropna(subset=["genotype_basecodes"]).copy()
    df["genotype_basecodes"] = df["genotype_basecodes"].astype(str).str.strip()
    df = df[df["genotype_basecodes"] != ""]
    if df.empty:
        print("[v11_seed_fish_genotypes_from_constructs] no fish with genotype_basecodes; nothing to do")
        return

    # 2) Upsert genotypes_v11 for each unique construct rollup
    uniq = df[["genotype_basecodes"]].drop_duplicates()

    with engine.begin() as cx:
        for _, row in uniq.iterrows():
            basecodes = row["genotype_basecodes"]
            cx.execute(
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
                    ON CONFLICT (genotype_code) DO NOTHING;
                    """
                ),
                {
                    "bc": basecodes,
                    # For now, use the basecodes string as a stand-in pretty label.
                    "pretty": basecodes,
                },
            )

    # 3) Build a LUT of genotype_basecodes -> genotype_id
    with engine.begin() as cx:
        genos = pd.read_sql(
            text(
                """
                SELECT id, genotype_basecodes
                FROM public.genotypes_v11
                """
            ),
            cx,
        )

    lut = dict(zip(genos["genotype_basecodes"], genos["id"]))

    # Map each fish to its target genotype_id
    df["target_gid"] = df["genotype_basecodes"].map(lut)
    df = df.dropna(subset=["target_gid"]).copy()
    if df.empty:
        print("[v11_seed_fish_genotypes_from_constructs] no matching genotypes_v11 rows for fish genotype_basecodes; nothing to do")
        return

    # Only update fish that don't already have a genotype_v11_id
    df_to_update = df[df["genotype_v11_id"].isna()].copy()
    if df_to_update.empty:
        print("[v11_seed_fish_genotypes_from_constructs] all fish already have genotype_v11_id; nothing to do")
        return

    updated = 0
    with engine.begin() as cx:
        for _, row in df_to_update.iterrows():
            res = cx.execute(
                text(
                    """
                    UPDATE public.fish_instances_v10 AS fi
                    SET genotype_v11_id = :gid
                    WHERE fi.id = :fid
                      AND (fi.genotype_v11_id IS NULL OR fi.genotype_v11_id <> :gid)
                    """
                ),
                {
                    "gid": row["target_gid"],
                    "fid": row["fish_id"],
                },
            )
            updated += res.rowcount

    print(f"[v11_seed_fish_genotypes_from_constructs] assigned genotype_v11_id for {updated} fish instance(s).")

if __name__ == "__main__":
    main()
