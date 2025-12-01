#!/usr/bin/env python3
from __future__ import annotations
import os
import argparse
from pathlib import Path
import pandas as pd
from sqlalchemy import create_engine, text

def get_engine():
    url = os.environ.get("DB_URL")
    if not url:
        raise SystemExit("DB_URL is not set")
    return create_engine(url)

def norm(s: object) -> str:
    if s is None:
        return ""
    return str(s).strip()

def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--csv", required=True, help="CSV with fish_code, transgene_base_code, allele_number, ...")
    args = p.parse_args()

    path = Path(args.csv)
    if not path.exists():
        raise SystemExit(f"[v11_load_fish_transgene_alleles] CSV not found: {path}")

    df = pd.read_csv(path)
    required_cols = {"fish_code", "transgene_base_code", "allele_number"}
    missing = required_cols - set(df.columns)
    if missing:
        raise SystemExit(f"[v11_load_fish_transgene_alleles] missing required columns: {sorted(missing)}")

    df = df.copy()
    df["fish_code"] = df["fish_code"].map(norm)
    df["transgene_base_code"] = df["transgene_base_code"].map(norm)
    df["allele_number"] = df["allele_number"].astype(int)

    df = df[(df["fish_code"] != "") & (df["transgene_base_code"] != "")]
    if df.empty:
        print("[v11_load_fish_transgene_alleles] no usable rows after basic filtering; nothing to do")
        return

    engine = get_engine()

    with engine.begin() as cx:
        # Build fish_code -> fish_id LUT
        fish = pd.read_sql(
            text("SELECT id::text AS fish_id, fish_code FROM public.fish_instances_v10"),
            cx,
        )
        fish_lut = dict(zip(fish["fish_code"], fish["fish_id"]))

        # Build construct_base_code -> construct_id LUT (for transgenes)
        constructs = pd.read_sql(
            text("SELECT id::text AS construct_id, base_code FROM public.constructs"),
            cx,
        )
        constructs_lut = {norm(bc): cid for bc, cid in zip(constructs["base_code"], constructs["construct_id"])}

        missing_fish = set()
        missing_constructs = set()
        inserted_transgenes = 0
        inserted_alleles = 0
        inserted_links = 0

        for _, row in df.iterrows():
            fish_code = norm(row["fish_code"])
            base_code = norm(row["transgene_base_code"])
            allele_number = int(row["allele_number"])

            fish_id = fish_lut.get(fish_code)
            if not fish_id:
                missing_fish.add(fish_code)
                continue

            # Ensure transgene exists (transgene_base_code FK -> constructs.base_code)
            if base_code not in constructs_lut:
                missing_constructs.add(base_code)
                continue

            cx.execute(
                text(
                    """
                    INSERT INTO public.transgenes (transgene_base_code, description, transgene_name)
                    VALUES (:bc, NULL, :bc)
                    ON CONFLICT (transgene_base_code) DO NOTHING;
                    """
                ),
                {"bc": base_code},
            )
            inserted_transgenes += 1  # approximate; we don't check rowcount here

            # Ensure transgene allele exists
            cx.execute(
                text(
                    """
                    INSERT INTO public.transgene_alleles (transgene_base_code, allele_number, allele_name)
                    VALUES (:bc, :allele_number, NULL)
                    ON CONFLICT (transgene_base_code, allele_number) DO NOTHING;
                    """
                ),
                {"bc": base_code, "allele_number": allele_number},
            )
            inserted_alleles += 1

            # Link fish to allele
            res = cx.execute(
                text(
                    """
                    INSERT INTO public.fish_transgene_alleles (fish_id, transgene_base_code, allele_number)
                    VALUES (:fish_id, :bc, :allele_number)
                    ON CONFLICT (fish_id, transgene_base_code, allele_number) DO NOTHING;
                    """
                ),
                {"fish_id": fish_id, "bc": base_code, "allele_number": allele_number},
            )
            inserted_links += res.rowcount

    if missing_fish:
        print("[v11_load_fish_transgene_alleles] WARN: fish_code not found for rows (skipped):", ", ".join(sorted(missing_fish)))
    if missing_constructs:
        print("[v11_load_fish_transgene_alleles] WARN: transgene_base_code not found in constructs (skipped):", ", ".join(sorted(missing_constructs)))

    print(f"[v11_load_fish_transgene_alleles] inserted/ensured transgenes ~{inserted_transgenes}, alleles ~{inserted_alleles}, links {inserted_links}")

if __name__ == "__main__":
    main()
