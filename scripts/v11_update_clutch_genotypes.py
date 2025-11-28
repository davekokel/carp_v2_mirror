#!/usr/bin/env python3
from __future__ import annotations

import sys, pathlib
import pandas as pd
from sqlalchemy import text

# ───────────────────────────────────────────
# Repo bootstrap
# ───────────────────────────────────────────
ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from carp_app.etl.util import get_engine_from_env

ROI_CSV = "seed_kits/legacy_wrangling_v2/working/legacy_imaging_annotations_for_db_v9.csv"


def main():
    print("[v11_update_clutch_genotypes] START")

    engine = get_engine_from_env()

    # --- Load legacy ROI CSV ---
    df = pd.read_csv(ROI_CSV)
    print(f"[v11_update_clutch_genotypes] Loaded ROI CSV: {len(df)} rows")

    # Normalize and extract columns
    if "legacy_clutch_key" not in df.columns:
        print("[v11_update_clutch_genotypes] ERROR: no legacy_clutch_key column in CSV")
        return

    # Clean keys
    df["legacy_clutch_key"] = (
        df["legacy_clutch_key"]
        .astype(str)
        .str.strip()
        .replace({"nan": "", "": None})
    )

    df = df.dropna(subset=["legacy_clutch_key"])
    print(f"[v11_update_clutch_genotypes] ROI rows with legacy_clutch_key: {len(df)}")

    # Extract genotype columns (if present)
    base_cols = [c for c in df.columns if c.lower() == "genotype_base_codes"]
    allele_cols = [c for c in df.columns if c.lower() == "genotype_allele_codes"]

    if not base_cols:
        print("[v11_update_clutch_genotypes] ERROR: genotype_base_codes column missing")
        return
    if not allele_cols:
        print("[v11_update_clutch_genotypes] ERROR: genotype_allele_codes column missing")
        return

    base_col = base_cols[0]
    allele_col = allele_cols[0]

    # Group by legacy clutch key
    grouped = df.groupby("legacy_clutch_key")
    updates = []

    for key, g in grouped:
        base_values = sorted({
            x for x in g[base_col].dropna().astype(str)
            if x.strip() not in ("", "nan")
        })
        allele_values = sorted({
            x for x in g[allele_col].dropna().astype(str)
            if x.strip() not in ("", "nan")
        })

        base_str = ",".join(base_values) if base_values else None
        allele_str = ",".join(allele_values) if allele_values else None

        updates.append((key, base_str, allele_str))

    print(f"[v11_update_clutch_genotypes] Unique legacy clutch keys: {len(updates)}")

    # Map legacy_clutch_key → clutch.id
    with engine.begin() as cx:
        clutch_df = pd.read_sql(
            text("SELECT id, clutch_code FROM public.clutches"),
            cx,
        )

    # Build mapping: legacy key prefix → clutch_code
    mapping = {}
    for _, row in clutch_df.iterrows():
        code = row["clutch_code"]
        if code and code.startswith("LCL-"):
            mapping_key = code.replace("LCL-", "")
            mapping[mapping_key] = row["clutch_code"]

    # Apply updates
    changed = 0
    with engine.begin() as cx:
        for legacy_key, base_str, allele_str in updates:
            # Legacy key looks like: "2025-05-28 | membrane xxx | membrane yyy"
            # The prefix before first " | " matches the clutch date.
            prefix = legacy_key.split("|")[0].strip().replace("-", "")
            clutch_code = mapping.get(prefix)

            if not clutch_code:
                continue

            cx.execute(
                text("""
                    UPDATE public.clutches
                    SET
                      genotype_base_codes = :base,
                      genotype_allele_codes = :allele
                    WHERE clutch_code = :code
                """),
                {
                    "code": clutch_code,
                    "base": base_str,
                    "allele": allele_str,
                }
            )
            changed += 1

    print(f"[v11_update_clutch_genotypes] Updated {changed} clutch rows.")
    print("[v11_update_clutch_genotypes] DONE.")


if __name__ == "__main__":
    main()
