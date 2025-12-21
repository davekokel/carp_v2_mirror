from __future__ import annotations

import re
import pandas as pd

SHEET = "seed_kits/legacy_wrangling_v3/working/imaging_sheet_augmented_v3.csv"
ROI_CSV = "seed_kits/legacy_wrangling_v3/working/legacy_imaging_annotations_for_db_v9_compat.csv"

OUT_OK = "seed_kits/legacy_wrangling_v3/working/exp_treatment_signatures.csv"
OUT_BAD = "seed_kits/legacy_wrangling_v3/working/exp_treatment_signatures_ambiguous.csv"

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
    # imaging sheet → dataset_key + signature
    df_sheet = pd.read_csv(SHEET, low_memory=False)
    df_sheet.columns = [c.strip() for c in df_sheet.columns]
    df_sheet["dataset_key"] = df_sheet["Data location"].map(key_from_sheet)
    df_sheet = df_sheet[df_sheet["dataset_key"] != ""].copy()

    df_sheet["pla"] = df_sheet["additional plasmids injected"].map(split_codes)
    df_sheet["rna"] = df_sheet["additional mRNAs injected"].map(split_codes)
    df_sheet["dye"] = df_sheet["additonal dye and chemicals"].map(split_codes)
    df_sheet["signature"] = df_sheet.apply(lambda r: sig(r.pla, r.rna, r.dye), axis=1)

    # identify ambiguous dataset_keys (more than one signature)
    sig_counts = df_sheet.groupby("dataset_key")["signature"].nunique().reset_index(name="n_signatures")
    bad_keys = set(sig_counts.loc[sig_counts["n_signatures"] > 1, "dataset_key"].astype(str).tolist())

    # ROI → dataset_key
    df_roi = pd.read_csv(ROI_CSV, low_memory=False)
    df_roi.columns = [c.strip() for c in df_roi.columns]
    df_roi["dataset_key"] = df_roi["roi_dir"].map(key_from_roi_dir)
    df_roi = df_roi[df_roi["dataset_key"] != ""].copy()
    df_roi["bruker_roi_id"] = df_roi["bruker_roi_id"].astype(str).str.strip()

    # Join (fanout) then split into OK vs BAD by dataset_key
    df_units = df_sheet[["dataset_key","signature"]].drop_duplicates()
    df_join = df_roi[["bruker_roi_id","dataset_key"]].merge(df_units, on="dataset_key", how="inner").drop_duplicates()

    df_bad = df_join[df_join["dataset_key"].isin(bad_keys)].sort_values(["dataset_key","bruker_roi_id","signature"]).reset_index(drop=True)
    df_ok  = df_join[~df_join["dataset_key"].isin(bad_keys)].sort_values(["dataset_key","signature","bruker_roi_id"]).reset_index(drop=True)

    df_ok.to_csv(OUT_OK, index=False)
    df_bad.to_csv(OUT_BAD, index=False)

    print("WROTE_OK", OUT_OK, "rows", len(df_ok), "dataset_keys", df_ok["dataset_key"].nunique(), "signatures", df_ok["signature"].nunique())
    print("WROTE_BAD", OUT_BAD, "rows", len(df_bad), "dataset_keys", df_bad["dataset_key"].nunique(), "signatures", df_bad["signature"].nunique())
    print("BAD_KEYS:")
    for k in sorted(bad_keys):
        print(" ", k)

if __name__ == "__main__":
    main()
