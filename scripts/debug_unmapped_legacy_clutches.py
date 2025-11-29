from __future__ import annotations

import pandas as pd

ANNOT = "seed_kits/legacy_wrangling_v2/working/legacy_imaging_annotations_for_db_v9.csv"
CLUTCHES = "seed_kits/legacy_wrangling_v2/working/legacy_clutches_v9.csv"
MAPPING = "seed_kits/legacy_wrangling_v2/working/clutch_treatment_mapping_v11.csv"

def main() -> None:
    df_ann = pd.read_csv(ANNOT)
    df_cl = pd.read_csv(CLUTCHES)
    df_map = pd.read_csv(MAPPING)

    all_keys = sorted(set(df_cl["legacy_clutch_key"].astype(str)))
    mapped_keys = sorted(set(df_map["legacy_clutch_key"].astype(str)))

    rna_cols = [
        "treatment_rna_rna_base_code",
        "treatment_rna_rna_base_code_from_enrich",
    ]
    plasmid_cols = [
        "treatment_plasmid_plasmid_base_code",
        "treatment_plasmid_plasmid_base_code_from_enrich",
    ]
    have_cols = [c for c in rna_cols + plasmid_cols if c in df_ann.columns]

    def has_any_basecodes(key: str) -> bool:
        rows = df_ann[df_ann["legacy_clutch_key"].astype(str) == key]
        if rows.empty:
            return False
        for c in have_cols:
            vals = rows[c].astype(str)
            if any(v.strip() not in ("", "nan") for v in vals):
                return True
        return False

    keys_with_any_tx = [k for k in all_keys if has_any_basecodes(k)]
    keys_with_no_tx = [k for k in all_keys if not has_any_basecodes(k)]

    keys_with_sig_no_mapping = sorted(set(keys_with_any_tx) - set(mapped_keys))

    print(f"Total legacy clutches (from CSV): {len(all_keys)}")
    print(f"Keys with any treatment basecodes in v9: {len(keys_with_any_tx)}")
    print(f"Keys with NO treatment basecodes in v9: {len(keys_with_no_tx)}")
    print(f"Keys mapped to T-LEGACY via mapping CSV: {len(mapped_keys)}")
    print(f"Keys with basecodes but NO T-LEGACY match: {len(keys_with_sig_no_mapping)}")

    print("\n[Clutches with no treatment basecodes in v9]:")
    for k in keys_with_no_tx:
        row = df_cl[df_cl["legacy_clutch_key"].astype(str) == k].iloc[0]
        print(f"  {row['clutch_code']}: {k}")

    print("\n[Clutches with basecodes but no T-LEGACY mix match]:")
    for k in keys_with_sig_no_mapping:
        row = df_cl[df_cl["legacy_clutch_key"].astype(str) == k].iloc[0]
        print(f"  {row['clutch_code']}: {k}")
        rows = df_ann[df_ann["legacy_clutch_key"].astype(str) == k]
        print("    basecodes:")
        for c in have_cols:
            vals = sorted(set(rows[c].astype(str)))
            vals = [v for v in vals if v.strip() not in ("", "nan")]
            if vals:
                print(f"      {c}: {vals}")

if __name__ == "__main__":
    main()
