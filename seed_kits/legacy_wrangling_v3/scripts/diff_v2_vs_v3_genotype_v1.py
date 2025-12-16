from __future__ import annotations

from pathlib import Path
import pandas as pd

ROOT = Path("/Users/davekokel/Projects/carp_v2")
V3 = ROOT / "seed_kits" / "legacy_wrangling_v3"
WORK = V3 / "working"
QC = V3 / "qc"
QC.mkdir(parents=True, exist_ok=True)

INP = WORK / "v3_roi_biology_map_v1.csv"
OUT = QC / "v2_vs_v3_genotype_diff_v1.csv"

def norm(x) -> str:
    if pd.isna(x):
        return ""
    s = str(x).strip()
    return "" if s.lower() in ("nan", "<na>", "none") else s

def main() -> None:
    df = pd.read_csv(INP)

    df["v2_base"] = df.get("v2_genotype_base_codes", "").apply(norm)
    df["v2_allele"] = df.get("v2_genotype_allele_codes", "").apply(norm)
    df["v3_fk"] = df.get("v3_resolved_alleles_fk", "").apply(norm)
    df["v3_status"] = df.get("v3_fk_resolve_status", "").apply(norm)

    def status_row(r):
        if r["v3_status"] == "ok":
            if r["v2_base"] and r["v2_allele"]:
                return "MATCHABLE_OK"
            return "MISSING_IN_V2_DERIVED"
        if r["v3_status"] == "no_pairing":
            if r["v2_base"] or r["v2_allele"]:
                return "V2_HAS_TEXT_BUT_NO_PAIRING_RULE"
            return "NO_DATA"
        if r["v3_status"] == "nickname_not_found":
            return "FK_LOOKUP_FAILED"
        return "UNKNOWN"

    df["diff_status"] = df.apply(status_row, axis=1)

    out_cols = [
        "bruker_roi_id",
        "experiment_folder",
        "roi_dir",
        "db_clutch_code",
        "v2_genotype_base_codes",
        "v2_genotype_allele_codes",
        "v3_fk_resolve_status",
        "v3_resolved_alleles_fk",
        "v3_genotype_cache_fk",
        "v3_genotype_code_fk",
        "v3_injected_mgco_codes",
        "diff_status",
    ]
    out_cols = [c for c in out_cols if c in df.columns]
    df[out_cols].to_csv(OUT, index=False)
    print("wrote", OUT, "rows:", len(df))

    print(df["diff_status"].value_counts(dropna=False).to_string())

if __name__ == "__main__":
    main()
