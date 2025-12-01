#!/usr/bin/env python3
from __future__ import annotations
import os
from itertools import combinations
from typing import List, Tuple, Dict, Set

import pandas as pd
from sqlalchemy import create_engine, text


def norm(s: object) -> str:
    if s is None:
        return ""
    return str(s).strip()


def get_engine():
    url = os.environ.get("DB_URL")
    if not url:
        raise SystemExit("DB_URL is not set")
    return create_engine(url)


def canonical_allele_key(base_code: str, nick: str, name: str) -> str:
    """
    Build a stable key for an allele using base_code + allele_nickname (preferred),
    falling back to allele_name (guN), then allele_number (already baked into name).
    """
    base = norm(base_code)
    n = norm(nick)
    if n:
        return f"{base}:{n}"
    # fall back to name (e.g. guN) if no nickname
    nm = norm(name)
    if nm:
        return f"{base}:{nm}"
    # last resort: just the base_code
    return f"{base}:"


def powerset(allele_keys: List[str]) -> List[List[str]]:
    """
    All subsets of allele_keys, including empty set, with canonical ordering.
    allele_keys must already be sorted.
    """
    out: List[List[str]] = []
    n = len(allele_keys)
    for r in range(0, n + 1):
        for combo in combinations(allele_keys, r):
            out.append(list(combo))
    return out


def main() -> None:
    engine = get_engine()

    with engine.begin() as cx:
        # 1) Load crosses that have parents and at least one clutch
        df_cross_clutch = pd.read_sql(
            text(
                """
                SELECT
                  x.id::text AS cross_id,
                  x.female_fish_id::text AS mother_id,
                  x.male_fish_id::text AS father_id,
                  c.id::text AS clutch_id
                FROM public.crosses x
                JOIN public.clutches c
                  ON c.cross_id = x.id
                WHERE x.female_fish_id IS NOT NULL
                  AND x.male_fish_id IS NOT NULL
                """
            ),
            cx,
        )

        if df_cross_clutch.empty:
            print("[v11_seed_clutch_expected_genotypes_from_parents] no crosses with parents + clutches; nothing to do")
            return

        # Group clutches by cross
        cross_to_clutches: Dict[str, List[str]] = {}
        mother_ids: Dict[str, str] = {}
        father_ids: Dict[str, str] = {}

        for _, r in df_cross_clutch.iterrows():
            cid = r["cross_id"]
            mother_ids[cid] = r["mother_id"]
            father_ids[cid] = r["father_id"]
            cross_to_clutches.setdefault(cid, []).append(r["clutch_id"])

        # 2) Pre-load alleles per fish_instance
        df_fish_alleles = pd.read_sql(
            text(
                """
                SELECT
                  fi.id::text AS fish_id,
                  ta.transgene_base_code,
                  ta.allele_number,
                  ta.allele_name,
                  ta.allele_nickname
                FROM public.fish_instances_v10 fi
                JOIN public.fish_transgene_alleles fta
                  ON fta.fish_id = fi.id
                JOIN public.transgene_alleles ta
                  ON ta.transgene_base_code = fta.transgene_base_code
                 AND ta.allele_number       = fta.allele_number
                """
            ),
            cx,
        )

        fish_to_alleles: Dict[str, Set[str]] = {}
        for _, r in df_fish_alleles.iterrows():
            fish_id = r["fish_id"]
            key = canonical_allele_key(
                r["transgene_base_code"],
                r["allele_nickname"],
                r["allele_name"],
            )
            if not key:
                continue
            fish_to_alleles.setdefault(fish_id, set()).add(key)

        # 3) Helper: get or create genotypes_v11 row for a given allele subset key
        def get_or_create_genotype_id(allele_keys: List[str]) -> str:
            # Canonical genotype_basecodes string
            if not allele_keys:
                gbc = ""  # empty subset (WT-ish)
            else:
                gbc = "||".join(allele_keys)

            # Try to find existing genotype by genotype_basecodes
            res = cx.execute(
                text(
                    """
                    SELECT id::text
                    FROM public.genotypes_v11
                    WHERE genotype_basecodes = :gbc
                    LIMIT 1
                    """
                ),
                {"gbc": gbc},
            ).fetchone()
            if res:
                return res[0]

            # Insert new genotype
            # Use the same code pattern as your fish genotype seeder: hash of basecodes
            res_ins = cx.execute(
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
                      'G-' || upper(encode(sha256(cast(:gbc as bytea)), 'hex'))::text,
                      :pretty,
                      :gbc,
                      now()
                    )
                    ON CONFLICT (genotype_code) DO NOTHING
                    RETURNING id::text
                    """
                ),
                {"gbc": gbc, "pretty": gbc if gbc else "WT"},
            )
            row = res_ins.fetchone()
            if row and row[0]:
                return row[0]

            # If ON CONFLICT hit, select again
            res2 = cx.execute(
                text(
                    """
                    SELECT id::text
                    FROM public.genotypes_v11
                    WHERE genotype_basecodes = :gbc
                    LIMIT 1
                    """
                ),
                {"gbc": gbc},
            ).fetchone()
            if not res2:
                raise SystemExit(f"[v11_seed_clutch_expected_genotypes_from_parents] failed to create/find genotype for basecodes='{gbc}'")
            return res2[0]

        total_crosses = 0
        total_clutches = 0
        total_genos_created = 0
        total_links_inserted = 0

        # 4) For each cross, compute possible child genotypes and attach to clutches
        for cross_id, clutch_ids in cross_to_clutches.items():
            mother_id = mother_ids.get(cross_id)
            father_id = father_ids.get(cross_id)
            if not mother_id or not father_id:
                continue

            mother_alleles = fish_to_alleles.get(mother_id, set())
            father_alleles = fish_to_alleles.get(father_id, set())
            if not mother_alleles and not father_alleles:
                # No allele info; still allow empty subset genotype
                union_keys: List[str] = []
            else:
                union_keys = sorted(mother_alleles.union(father_alleles))

            # All subsets (including empty)
            subset_list = powerset(union_keys)
            geno_ids: List[str] = []

            for subset in subset_list:
                # subset is a list of canonical allele_keys (already sorted by powerset)
                gid = get_or_create_genotype_id(subset)
                geno_ids.append(gid)

            total_crosses += 1
            total_clutches += len(clutch_ids)
            total_genos_created += len(set(geno_ids))

            # Link each genotype to each clutch from this cross
            for cid in clutch_ids:
                for gid in geno_ids:
                    res = cx.execute(
                        text(
                            """
                            INSERT INTO public.clutch_genotypes_v11 (
                              clutch_id,
                              genotype_v11_id,
                              expected_fraction,
                              expected_label,
                              notes,
                              created_by
                            ) VALUES (
                              :cid,
                              :gid,
                              NULL,
                              'possible',
                              'seed_from_parent_allele_powerset_v11',
                              'v11_seed_clutch_expected_genotypes_from_parents'
                            )
                            ON CONFLICT (clutch_id, genotype_v11_id) DO NOTHING;
                            """
                        ),
                        {"cid": cid, "gid": gid},
                    )
                    total_links_inserted += res.rowcount

    print(f"[v11_seed_clutch_expected_genotypes_from_parents] crosses processed: {total_crosses}")
    print(f"[v11_seed_clutch_expected_genotypes_from_parents] clutches covered: {total_clutches}")
    print(f"[v11_seed_clutch_expected_genotypes_from_parents] unique genotype subsets per run (per cross union): ~{total_genos_created}")
    print(f"[v11_seed_clutch_expected_genotypes_from_parents] clutch_genotypes_v11 links inserted: {total_links_inserted}")


if __name__ == "__main__":
    main()
