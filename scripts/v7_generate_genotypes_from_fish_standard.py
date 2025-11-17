#!/usr/bin/env python
from __future__ import annotations

import sys
import pathlib
from pathlib import Path
import re

import pandas as pd


NA_TOKENS = {"", "nan", "na", "n/a", "none", "-", "?"}


def make_genotype_code(base: str, allele_nick: str) -> str:
    s = f"{base}_{allele_nick}"
    s = s.replace(" ", "_")
    s = re.sub(r"[^A-Za-z0-9_]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return f"GT_STD_{s}"


def is_real_token(s: str) -> bool:
    return s.strip().lower() not in NA_TOKENS


def main(argv: list[str] | None = None) -> int:
    base = Path("seed_kits/2025-11-15-121231-autoload")
    fish_path = base / "fish.xlsx"

    if not fish_path.exists():
        print(f"fish.xlsx not found at {fish_path}", file=sys.stderr)
        return 1

    print(f"Reading {fish_path} ...")
    df = pd.read_excel(fish_path)
    print("Fish columns:", list(df.columns))

    df = df.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]

    required = [
        "birthday",
        "genetic_background",
        "nickname",
        "line_building_stage",
        "transgene_base_code",
        "allele_nickname",
        "zygosity",
    ]
    missing = [c for c in required if c not in df.columns]
    if missing:
        print(f"ERROR: fish.xlsx missing required columns: {missing}", file=sys.stderr)
        return 1

    df["transgene_base_code"] = df["transgene_base_code"].astype(str).str.strip()
    df["allele_nickname"] = df["allele_nickname"].astype(str).str.strip()
    df["zygosity"] = df["zygosity"].astype(str).str.strip()
    df["genetic_background"] = df["genetic_background"].astype(str).str.strip()
    df["nickname"] = df["nickname"].astype(str).str.strip()

    # Require real base + allele_nickname (not NA-ish)
    mask_has_geno = df.apply(
        lambda r: is_real_token(r["transgene_base_code"]) and is_real_token(r["allele_nickname"]),
        axis=1,
    )
    df_geno = df[mask_has_geno].copy()
    print(f"Rows with real genotype info: {len(df_geno)} of {len(df)}")

    if df_geno.empty:
        print("No real genotype info found; nothing to write.")
        return 0

    df_geno["genotype_key"] = list(
        zip(df_geno["transgene_base_code"], df_geno["allele_nickname"])
    )

    grouped = (
        df_geno.groupby("genotype_key")
        .agg(
            genetic_background=("genetic_background", "first"),
            sample_nicks=("nickname", lambda s: ", ".join(sorted({x for x in s if x})[:3])),
        )
        .reset_index()
    )

    genotype_rows = []
    allele_rows = []

    for (base_code, allele_nick), row in grouped.set_index("genotype_key").iterrows():
        g_code = make_genotype_code(base_code, allele_nick)
        g_name = f"{base_code} {allele_nick}"
        bg = row["genetic_background"] or ""
        sample_nicks = row["sample_nicks"] or ""
        notes = "from standard fish.xlsx"
        if sample_nicks:
            notes += f"; sample nicknames: {sample_nicks}"

        genotype_rows.append(
            {
                "genotype_code": g_code,
                "genotype_name": g_name,
                "genetic_background": bg,
                "source_system": "standard",
                "notes": notes,
            }
        )

        allele_rows.append(
            {
                "genotype_code": g_code,
                "transgene_base_code": base_code,
                "allele_nickname": allele_nick,
                "zygosity": "",
            }
        )

    df_genotypes = pd.DataFrame(genotype_rows)
    df_genotype_alleles = pd.DataFrame(allele_rows)

    geno_out = base / "genotypes_from_standard_fish.csv"
    geno_alleles_out = base / "genotype_alleles_from_standard_fish.csv"

    df_genotypes.to_csv(geno_out, index=False)
    df_genotype_alleles.to_csv(geno_alleles_out, index=False)

    print()
    print("Genotypes derived:", len(df_genotypes))
    print(df_genotypes.head())
    print()
    print("Genotype-alleles rows:", len(df_genotype_alleles))
    print(df_genotype_alleles.head())
    print()
    print("Wrote:")
    print(" ", geno_out)
    print(" ", geno_alleles_out)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
