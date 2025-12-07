#!/usr/bin/env python3
from __future__ import annotations

import os

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


def get_engine() -> Engine:
    url = os.environ.get("DB_URL")
    if not url:
        raise SystemExit("DB_URL must be set")
    print(f"DB_URL={url}")
    return create_engine(url)


def main() -> None:
    eng = get_engine()

    # 1. Load 12 clutches with NULL genotype_v11_id
    with eng.begin() as cx:
        df_clutches = pd.read_sql(
            text(
                """
                SELECT
                  c.id::text        AS clutch_id,
                  c.clutch_code,
                  c.clutch_date
                FROM public.clutches c
                WHERE c.source_system = 'legacy_imaging'
                  AND c.genotype_v11_id IS NULL
                ORDER BY c.clutch_code
                """
            ),
            cx,
        )

        df_parents = pd.read_sql(
            text(
                """
                SELECT
                  clutch_code,
                  parent_female_label,
                  parent_female_allele,
                  parent_male_label,
                  parent_male_allele
                FROM raw.legacy_clutch_parents_v9
                """
            ),
            cx,
        )

        df_defs = pd.read_sql(
            text(
                """
                SELECT
                  parent_fish_name,
                  plasmid_base_code,
                  allele,
                  injected_rna,
                  injected_plasmid
                FROM raw.legacy_parent_definitions_v9
                """
            ),
            cx,
        )

    # 2. Join clutches -> parents
    df = df_clutches.merge(df_parents, on="clutch_code", how="left")

    # 3. Prepare parent definition lookup
    # We join by parent_fish_name == parent_female_label / parent_male_label (string match)
    df_defs["parent_fish_name"] = df_defs["parent_fish_name"].astype(str).str.strip()

    def lookup_parent(name: str):
        if not name or str(name).lower() == "nan":
            return []
        name = str(name).strip()
        sub = df_defs.loc[df_defs["parent_fish_name"] == name]
        if sub.empty:
            return []
        rows = []
        for _, row in sub.iterrows():
            rows.append(
                {
                    "plasmid_base_code": (row["plasmid_base_code"] or "").strip() or None,
                    "allele": (str(row["allele"]).strip() if row["allele"] not in (None, "", "nan") else None),
                    "injected_rna": (row["injected_rna"] or "").strip() or None,
                    "injected_plasmid": (row["injected_plasmid"] or "").strip() or None,
                }
            )
        return rows

    records = []
    for _, row in df.iterrows():
        clutch_code = row["clutch_code"]
        clutch_date = row["clutch_date"]
        f_label = row.get("parent_female_label")
        m_label = row.get("parent_male_label")

        f_defs = lookup_parent(f_label)
        m_defs = lookup_parent(m_label)

        f_plasmids = {r["plasmid_base_code"] for r in f_defs if r["plasmid_base_code"]}
        m_plasmids = {r["plasmid_base_code"] for r in m_defs if r["plasmid_base_code"]}
        f_rnas = {r["injected_rna"] for r in f_defs if r["injected_rna"]}
        m_rnas = {r["injected_rna"] for r in m_defs if r["injected_rna"]}

        parent_plasmids = sorted(f_plasmids | m_plasmids)
        parent_rnas = sorted(f_rnas | m_rnas)

        records.append(
            {
                "clutch_code": clutch_code,
                "clutch_date": clutch_date,
                "parent_female_label": f_label,
                "parent_male_label": m_label,
                "parent_plasmid_basecodes": ",".join(parent_plasmids) if parent_plasmids else "",
                "parent_injected_rna": ",".join(parent_rnas) if parent_rnas else "",
            }
        )

    out = pd.DataFrame(records)
    print("[PREVIEW] Parent-based genotype candidates for legacy clutches with NULL genotype_v11_id:")
    print(out.to_string(index=False))


if __name__ == "__main__":
    main()
