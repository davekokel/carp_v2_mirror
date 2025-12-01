#!/usr/bin/env python3
from __future__ import annotations
import os
import hashlib

import pandas as pd
from sqlalchemy import create_engine, text


def get_engine():
    url = os.environ.get("DB_URL")
    if not url:
        raise SystemExit("DB_URL is not set")
    return create_engine(url)


def mk_genotype_code(basecodes: str) -> str:
    h = hashlib.sha256(basecodes.encode("utf-8")).hexdigest().upper()
    return "G-" + h[:10]


def main() -> None:
    engine = get_engine()

    with engine.begin() as cx:
        df = pd.read_sql(
            text(
                """
                WITH constructs AS (
                  SELECT
                    r.fish_instance_id,
                    r.fish_code,
                    r.genotype_basecodes
                  FROM public.v11_fish_construct_rollups r
                  WHERE r.genotype_basecodes IS NOT NULL
                    AND r.genotype_basecodes <> ''
                ),
                alleles AS (
                  SELECT
                    fta.fish_id AS fish_instance_id,
                    string_agg(
                      DISTINCT
                        ta.transgene_base_code
                        || ':' ||
                        COALESCE(
                          ta.allele_name,
                          'gu' || ta.allele_number::text
                        )
                        || CASE
                             WHEN ta.allele_nickname IS NOT NULL
                                  AND ta.allele_nickname <> ''
                             THEN '(' || ta.allele_nickname || ')'
                             ELSE ''
                           END,
                      '||'
                      ORDER BY
                        ta.transgene_base_code
                        || ':' ||
                        COALESCE(
                          ta.allele_name,
                          'gu' || ta.allele_number::text
                        )
                        || CASE
                             WHEN ta.allele_nickname IS NOT NULL
                                  AND ta.allele_nickname <> ''
                             THEN '(' || ta.allele_nickname || ')'
                             ELSE ''
                           END
                    ) AS allele_rollup
                  FROM public.fish_transgene_alleles fta
                  JOIN public.transgene_alleles ta
                    ON ta.transgene_base_code = fta.transgene_base_code
                   AND ta.allele_number       = fta.allele_number
                  GROUP BY fta.fish_id
                )
                SELECT
                  c.fish_instance_id,
                  c.fish_code,
                  c.genotype_basecodes,
                  a.allele_rollup
                FROM constructs c
                LEFT JOIN alleles a
                  ON a.fish_instance_id = c.fish_instance_id
                """
            ),
            cx,
        )

    if df.empty:
        print("[v11_seed_fish_genotypes_from_constructs] no fish with construct rollups; nothing to do")
        return

    df["genotype_basecodes"] = (
        df["genotype_basecodes"].astype(str).str.strip()
    )
    df = df[df["genotype_basecodes"] != ""].copy()

    df["allele_rollup"] = df["allele_rollup"].astype("string")

    df_unique = (
        df[["genotype_basecodes", "allele_rollup"]]
        .drop_duplicates(subset=["genotype_basecodes"])
        .reset_index(drop=True)
    )
    df_unique["genotype_code"] = df_unique["genotype_basecodes"].apply(
        mk_genotype_code
    )
    df_unique["genotype_pretty"] = df_unique["allele_rollup"].where(
        df_unique["allele_rollup"].notna()
        & (df_unique["allele_rollup"].astype(str) != ""),
        df_unique["genotype_basecodes"],
    )

    code_to_id: dict[str, str] = {}

    with engine.begin() as cx:
        for _, r in df_unique.iterrows():
            basecodes = r["genotype_basecodes"]
            code = r["genotype_code"]
            pretty = r["genotype_pretty"]

            res = cx.execute(
                text(
                    """
                    INSERT INTO public.genotypes_v11 (
                      genotype_code,
                      genotype_pretty,
                      genotype_basecodes,
                      source_system
                    )
                    VALUES (:code, :pretty, :basecodes, 'v11_fish_alleles')
                    ON CONFLICT (genotype_code) DO UPDATE
                    SET genotype_pretty    = EXCLUDED.genotype_pretty,
                        genotype_basecodes = EXCLUDED.genotype_basecodes
                    RETURNING id
                    """
                ),
                {"code": code, "pretty": pretty, "basecodes": basecodes},
            )
            gid = res.scalar()
            if gid is None:
                gid = cx.execute(
                    text(
                        """
                        SELECT id
                        FROM public.genotypes_v11
                        WHERE genotype_code = :code
                        """
                    ),
                    {"code": code},
                ).scalar()
            if gid is not None:
                code_to_id[code] = str(gid)

    if not code_to_id:
        print("[v11_seed_fish_genotypes_from_constructs] no genotypes_v11 rows created/updated; nothing to do")
        return

    df = df.copy()
    df["genotype_code"] = df["genotype_basecodes"].apply(mk_genotype_code)

    updated = 0
    with engine.begin() as cx:
        for _, r in df.iterrows():
            fid = r["fish_instance_id"]
            code = r["genotype_code"]
            gid = code_to_id.get(code)
            if gid is None:
                continue
            res = cx.execute(
                text(
                    """
                    UPDATE public.fish_instances_v10 AS fi
                    SET genotype_v11_id = :gid
                    WHERE fi.id = :fid
                      AND (fi.genotype_v11_id IS NULL OR fi.genotype_v11_id <> :gid)
                    """
                ),
                {"gid": gid, "fid": fid},
            )
            updated += res.rowcount

    print(
        f"[v11_seed_fish_genotypes_from_constructs] assigned genotype_v11_id for {updated} fish instance(s)."
    )


if __name__ == "__main__":
    main()
