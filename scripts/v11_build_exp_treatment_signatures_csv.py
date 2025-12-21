from __future__ import annotations

import re
import pandas as pd

SHEET = "seed_kits/legacy_wrangling_v2/raw/2025-11-21-220012-imaging_sheet.xlsx"
ROI_CSV = "seed_kits/legacy_wrangling_v3/working/legacy_imaging_annotations_for_db_v9_compat.csv"
OUT = "seed_kits/legacy_wrangling_v3/working/exp_treatment_signatures.csv"

re_sheet = re.compile(r"(Aang_Foundation|Korra_Foundation|Exploratory_fish)[/\\](\d{8}[^/\\]+)", re.I)
re_roi = re.compile(r"/(Aang_Foundation|Korra_Foundation|Exploratory_fish)/(\d{8}[^/]+)/", re.I)

def norm(x):
    if x is None:
        return ""
    s = str(x).strip()
    if s.lower() in ("nan","none"):
        return ""
    return s

def split_codes(x):
    s = norm(x).replace("|", ",")
    parts = [p.strip().lower() for p in s.split(",") if p.strip()]
    return sorted(set(parts))

def key_from_sheet(path):
    m = re_sheet.search(norm(path))
    return f"{m.group(1)}/{m.group(2)}" if m else ""

def key_from_roi_dir(path):
    m = re_roi.search(norm(path))
    return f"{m.group(1)}/{m.group(2)}" if m else ""

def sig(plas, rnas, dyes):
    return f"plasmids={','.join(plas)}|rnas={','.join(rnas)}|dyes={','.join(dyes)}"

def main():
    df_sheet = pd.read_excel(SHEET, sheet_name="Sheet1")
    df_sheet.columns = [c.strip() for c in df_sheet.columns]
    df_sheet["dataset_key"] = df_sheet["Data location"].map(key_from_sheet)
    df_sheet = df_sheet[df_sheet["dataset_key"] != ""].copy()

    df_sheet["pla"] = df_sheet["additional plasmids injected"].map(split_codes)
    df_sheet["rna"] = df_sheet["additional mRNAs injected"].map(split_codes)
    df_sheet["dye"] = df_sheet["additonal dye and chemicals"].map(split_codes)
    df_sheet["signature"] = df_sheet.apply(lambda r: sig(r.pla, r.rna, r.dye), axis=1)

    # Reduce to unique experiment-treatment units
    df_units = df_sheet[["dataset_key","signature"]].drop_duplicates().sort_values(["dataset_key","signature"]).reset_index(drop=True)

    df_roi = pd.read_csv(ROI_CSV, low_memory=False)
    df_roi.columns = [c.strip() for c in df_roi.columns]
    df_roi["dataset_key"] = df_roi["roi_dir"].map(key_from_roi_dir)
    df_roi = df_roi[df_roi["dataset_key"] != ""].copy()

    # Join by dataset_key (fanout)
    df_join = df_roi[["bruker_roi_id","dataset_key"]].dropna().merge(df_units, on="dataset_key", how="inner")
    df_join["bruker_roi_id"] = df_join["bruker_roi_id"].astype(str).str.strip()

    # Output is ROI-level mapping to experiment-treatment unit
    out = df_join.drop_duplicates().sort_values(["dataset_key","signature","bruker_roi_id"]).reset_index(drop=True)
    out.to_csv(OUT, index=False)
    print("WROTE", OUT, "rows", len(out), "unique_dataset_keys", out["dataset_key"].nunique(), "unique_signatures", out["signature"].nunique())

if __name__ == "__main__":
    main()
