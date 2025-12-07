#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import os
from typing import Dict, List, Optional, Set

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


def get_engine() -> Engine:
    url = os.environ.get("DB_URL")
    if not url:
        raise SystemExit("DB_URL must be set")
    print(f"DB_URL={url}")
    return create_engine(url)


def load_missing_legacy_clutches(engine: Engine) -> pd.DataFrame:
    sql = text(
        """
        SELECT
          c.id::text AS clutch_id,
          c.clutch_code,
          c.clutch_date
        FROM public.clutches c
        WHERE c.source_system = 'legacy_imaging'
          AND c.genotype_v11_id IS NULL
        ORDER BY c.clutch_code;
        """
    )
    with engine.begin() as cx:
        return pd.read_sql(sql, cx)


def load_clutch_parents(engine: Engine) -> pd.DataFrame:
    sql = text(
        """
        SELECT
          clutch_code,
          parent_female_label,
          parent_female_allele,
          parent_male_label,
          parent_male_allele
        FROM raw.legacy_clutch_parents_v9;
        """
    )
    with engine.begin() as cx:
        return pd.read_sql(sql, cx)


def load_parent_definitions(engine: Engine) -> pd.DataFrame:
    sql = text(
        """
        SELECT
          parent_fish_name,
          plasmid_base_code,
          allele,
          injected_rna,
          injected_plasmid
        FROM raw.legacy_parent_definitions_v9;
        """
    )
    with engine.begin() as cx:
        df = pd.read_sql(sql, cx)
    for col in ["parent_fish_name", "plasmid_base_code", "allele", "injected_rna", "injected_plasmid"]:
        df[col] = df[col].astype(str).str.strip().where(df[col].notna(), None)
    return df


def lookup_parent(defs: pd.DataFrame, label: Optional[str]) -> List[Dict[str, Optional[str]]]:
    if label is None:
        return []
    s = str(label).strip()
    if not s or s.lower() == "nan":
        return []
    sub = defs.loc[defs["parent_fish_name"] == s]
    if sub.empty:
        return []
    rows: List[Dict[str, Optional[str]]] = []
    for _, row in sub.iterrows():
        rows.append(
            {
                "plasmid_base_code": (row["plasmid_base_code"] or "").strip() or None,
                "allele": (row["allele"] or "").strip() or None,
                "injected_rna": (row["injected_rna"] or "").strip() or None,
                "injected_plasmid": (row["injected_plasmid"] or "").strip() or None,
            }
        )
    return rows


def load_existing_genotypes(engine: Engine) -> Dict[str, str]:
    sql = text(
        """
        SELECT id::text AS genotype_id,
               genotype_basecodes
        FROM public.genotypes_v11;
        """
    )
    with engine.begin() as cx:
        df = pd.read_sql(sql, cx)

    mapping: Dict[str, str] = {}
    for _, row in df.iterrows():
        base = (row["genotype_basecodes"] or "").strip()
        if not base:
            continue
        mapping[base] = row["genotype_id"]
    print(f"[v11_seed_legacy_genotypes_from_parents] existing genotypes: {len(mapping)}")
    return mapping


def ensure_genotype(
    engine: Engine,
    basecodes: str,
    existing: Dict[str, str],
) -> str:
    base = basecodes.strip()
    if not base:
        raise ValueError("empty basecodes in ensure_genotype")

    if base in existing:
        return existing[base]

    h = hashlib.sha1(base.encode("utf-8")).hexdigest()[:8]
    genotype_code = f"LEGACY-PARENT-{h}"
    genotype_pretty = base

    with engine.begin() as cx:
        gid = cx.execute(
            text(
                """
                INSERT INTO public.genotypes_v11 (
                  id,
                  genotype_code,
                  genotype_pretty,
                  genotype_basecodes,
                  created_at,
                  legacy_label,
                  source_system
                )
                VALUES (
                  gen_random_uuid(),
                  :genotype_code,
                  :genotype_pretty,
                  :genotype_basecodes,
                  now(),
                  :legacy_label,
                  'legacy_parent_inference_v9'
                )
                RETURNING id::text;
                """
            ),
            {
                "genotype_code": genotype_code,
                "genotype_pretty": genotype_pretty,
                "genotype_basecodes": base,
                "legacy_label": base,
            },
        ).scalar()

    existing[base] = gid
    print(f"[v11_seed_legacy_genotypes_from_parents] created genotype {gid} for basecodes='{base}'")
    return gid


def apply_parent_based_genotypes(engine: Engine) -> None:
    missing = load_missing_legacy_clutches(engine)
    parents = load_clutch_parents(engine)
    defs = load_parent_definitions(engine)
    existing = load_existing_genotypes(engine)

    df = missing.merge(parents, on="clutch_code", how="left")

    records: List[Dict[str, str]] = []

    for _, row in df.iterrows():
        clutch_id = row["clutch_id"]
        clutch_code = row["clutch_code"]
        f_label = row.get("parent_female_label")
        m_label = row.get("parent_male_label")

        f_defs = lookup_parent(defs, f_label)
        m_defs = lookup_parent(defs, m_label)

        f_plasmids: Set[str] = {r["plasmid_base_code"] for r in f_defs if r["plasmid_base_code"]}
        m_plasmids: Set[str] = {r["plasmid_base_code"] for r in m_defs if r["plasmid_base_code"]}

        parent_plasmids = sorted(f_plasmids | m_plasmids)

        if not parent_plasmids:
            print(f"[v11_seed_legacy_genotypes_from_parents] no parent plasmids for clutch {clutch_code}, skipping")
            continue

        basecodes_str = ",".join(parent_plasmids)
        records.append(
            {
                "clutch_id": clutch_id,
                "clutch_code": clutch_code,
                "basecodes": basecodes_str,
            }
        )

    if not records:
        print("[v11_seed_legacy_genotypes_from_parents] no clutches with parent plasmid basecodes to update")
        return

    df_rec = pd.DataFrame(records)
    print("[v11_seed_legacy_genotypes_from_parents] candidate parent-based genotypes:")
    print(df_rec.to_string(index=False))

    updated = 0
    with engine.begin() as cx:
        for _, row in df_rec.iterrows():
            clutch_id = row["clutch_id"]
            clutch_code = row["clutch_code"]
            basecodes = row["basecodes"]

            gid_before = cx.execute(
                text(
                    """
                    SELECT genotype_v11_id::text
                    FROM public.clutches
                    WHERE id = :cid;
                    """
                ),
                {"cid": clutch_id},
            ).scalar()

            if gid_before:
                print(f"[v11_seed_legacy_genotypes_from_parents] clutch {clutch_code} already has genotype, skipping")
                continue

            gid = ensure_genotype(engine, basecodes, existing)

            res = cx.execute(
                text(
                    """
                    UPDATE public.clutches
                    SET genotype_v11_id = :gid
                    WHERE id = :cid
                      AND genotype_v11_id IS NULL;
                    """
                ),
                {"gid": gid, "cid": clutch_id},
            )
            updated += res.rowcount

    print(f"[v11_seed_legacy_genotypes_from_parents] set genotype_v11_id for {updated} clutch(es)")


def main() -> None:
    eng = get_engine()
    apply_parent_based_genotypes(eng)

    with eng.begin() as cx:
        n_clutches, n_with = cx.execute(
            text(
                """
                SELECT count(*) AS n_clutches,
                       count(genotype_v11_id) AS n_with_genotype
                FROM public.clutches
                WHERE source_system = 'legacy_imaging';
                """
            )
        ).one()
    print(
        f"[v11_seed_legacy_genotypes_from_parents] SUMMARY: legacy clutches={n_clutches}, with genotype_v11_id={n_with}"
    )


if __name__ == "__main__":
    main()
