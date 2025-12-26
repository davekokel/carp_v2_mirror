from __future__ import annotations

import os
from pathlib import Path
import pandas as pd
from sqlalchemy import create_engine, text

EMPTY_SIG = "plasmids=|rnas=|dyes="

IDEAL_TSV = "seed_kits/legacy_wrangling_v4/working/ideal_imaging_import_sheet_v4.fixed.tsv"
OUT_DIR = Path("seed_kits/legacy_wrangling_v4/qc")

def s(x) -> str:
    if x is None:
        return ""
    return str(x).strip()

def main() -> None:
    db_url = os.environ.get("DB_URL")
    if not db_url:
        raise SystemExit("[STOP] DB_URL not set")

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # ---- load ideal ----
    ideal = pd.read_csv(IDEAL_TSV, sep="\t", dtype=str).fillna("")
    ideal.columns = [c.strip() for c in ideal.columns]

    need = [
        "roi_path",
        "genotype_base_codes",
        "genotype_allele_codes",
        "treatment_plasmid_base_codes",
        "treatment_rna_base_codes",
        "locked_genotype",
        "locked_treatment",
    ]
    for c in need:
        if c not in ideal.columns:
            raise SystemExit(f"[STOP] ideal missing column: {c}")

    # infer clutch_code from DB
    eng = create_engine(db_url)

    with eng.begin() as cx:
        clutch_map = pd.read_sql(
            text("""
              SELECT DISTINCT
                ira.roi_path,
                c.id AS clutch_id,
                c.clutch_code
              FROM public.imaging_roi_annotations ira
              JOIN public.imaging_clutch_memberships m ON m.slot_id = ira.slot_id
              JOIN public.clutches c ON c.id = m.clutch_id
            """),
            cx,
        )

    ideal = ideal.merge(clutch_map, on="roi_path", how="left")

    # ---- expectations ----
    ideal["expect_genotype"] = (
        (ideal["genotype_base_codes"].map(s) != "")
        | (ideal["locked_genotype"].str.lower().str.startswith("t"))
    ).astype(int)

    ideal["signature_text"] = ideal.get("signature_text", "").map(s)
    ideal["expect_treatment"] = (
        (ideal["signature_text"] != EMPTY_SIG)
        | (ideal["treatment_plasmid_base_codes"].map(s) != "")
        | (ideal["treatment_rna_base_codes"].map(s) != "")
    ).astype(int)
    per_clutch_expect = (
        ideal
        .groupby(["clutch_id", "clutch_code"], dropna=False)
        .agg(
            expect_genotype=("expect_genotype", "max"),
            expect_treatment=("expect_treatment", "max"),
            example_roi_path=("roi_path", "min"),
        )
        .reset_index()
    )

    # ---- actual DB state ----
    with eng.begin() as cx:
        have_geno = pd.read_sql(
            text("SELECT id AS clutch_id, genotype_v11_id IS NOT NULL AS has_genotype FROM public.clutches"),
            cx,
        )

        have_treat = pd.read_sql(
            text("""
              SELECT j.clutch_id, 1 AS has_treatment
              FROM public.join_clutch_treatments j
              JOIN public.treatments t ON t.id = j.treatment_id
              WHERE btrim(t.treat_text) <> 'plasmids=|rnas=|dyes='
              GROUP BY 1
            """),
            cx,
        )

    qc = (
        per_clutch_expect
        .merge(have_geno, on="clutch_id", how="left")
        .merge(have_treat, on="clutch_id", how="left")
        .fillna({"has_genotype": False, "has_treatment": 0})
    )

    qc["has_treatment"] = qc["has_treatment"].astype(int)

    qc["is_bad"] = (
        (qc["expect_genotype"] == 1) & (~qc["has_genotype"])
        | (qc["expect_treatment"] == 1) & (qc["has_treatment"] != 1)
    )

    # ---- outputs ----
    qc.to_csv(OUT_DIR / "qc_vs_ideal_summary.csv", index=False)

    qc[(qc["expect_genotype"] == 1) & (~qc["has_genotype"])][
        ["clutch_code", "example_roi_path"]
    ].to_csv(OUT_DIR / "patch_missing_genotypes.csv", index=False)

    qc[(qc["expect_treatment"] == 1) & (qc["has_treatment"] != 1)][
        ["clutch_code", "example_roi_path"]
    ].to_csv(OUT_DIR / "patch_missing_treatments.csv", index=False)

    print("[OK] QC complete")
    print("  ", OUT_DIR / "qc_vs_ideal_summary.csv")
    print("  ", OUT_DIR / "patch_missing_genotypes.csv")
    print("  ", OUT_DIR / "patch_missing_treatments.csv")

if __name__ == "__main__":
    main()
