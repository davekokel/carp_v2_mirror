from __future__ import annotations

from pathlib import Path
import re
import pandas as pd

ROOT = Path("~/Projects/carp_v2/seed_kits/legacy_wrangling_v5").expanduser()
RAW = ROOT / "raw"
WORKING = ROOT / "working"
QC = ROOT / "qc_runs"

IN_XLSX = RAW / "2025-12-22-161955-Cell Observatory - Zebrafish Development.xlsx"
SHEET = "Master Imaging list"
IN_SLUGS = WORKING / "roi_path_slugs_v5.csv"

OUT_LINK = WORKING / "experiment_linkage_v5.tsv"
OUT_CAND = WORKING / "experiment_linkage_v5_candidates.tsv"
OUT_QC = QC / "experiment_linkage_v5.qc.tsv"

RE_DATE8 = re.compile(r"^(\d{8})")

def norm_path(s: str) -> str:
    return str(s).strip().replace("\\", "/")

def exp_date_from_folder(folder: str) -> str:
    m = RE_DATE8.match(str(folder))
    return m.group(1) if m else ""

def to_yyyymmdd(v) -> str:
    ts = pd.to_datetime(v, errors="coerce")
    if pd.isna(ts):
        return ""
    return ts.strftime("%Y%m%d")

def main() -> None:
    slugs = pd.read_csv(IN_SLUGS)
    exp = slugs.drop_duplicates(subset=["foundation_root","experiment_folder"])[
        ["foundation_root","experiment_folder","experiment_slug"]
    ].copy()
    exp["experiment_date"] = exp["experiment_folder"].map(exp_date_from_folder)

    x = pd.read_excel(IN_XLSX, sheet_name=SHEET)
    for c in [
        "Data location",
        "date_mount",
        "Date imaged",
        "ZF female genotype",
        "ZF male genotype",
        "additional plasmids injected",
        "additional mRNAs injected",
        "additonal dye and chemicals",
        "free_text_label",
        "comments",
    ]:
        if c not in x.columns:
            x[c] = ""

    x = x.copy()
    x["Data_location_norm"] = x["Data location"].astype(str).map(norm_path)
    x["foundation_root"] = x["Data_location_norm"].str.extract(r"(Aang_Foundation|Korra_Foundation)")[0].fillna("")
    x["date_mount_yyyymmdd"] = x["date_mount"].map(to_yyyymmdd)
    x["date_imaged_yyyymmdd"] = x["Date imaged"].map(to_yyyymmdd)
    x["blob"] = x[["Data_location_norm","free_text_label","comments"]].astype(str).agg(" | ".join, axis=1)

    rows = []
    cand_rows = []

    for _, r in exp.iterrows():
        fr = r["foundation_root"]
        ef = r["experiment_folder"]
        slug = str(r.get("experiment_slug") or "")
        d = str(r.get("experiment_date") or "")

        cand1 = x[(x["foundation_root"] == fr) & (x["Data_location_norm"].str.contains(ef, na=False))]
        cand2 = x[(x["foundation_root"] == fr) & (x["date_mount_yyyymmdd"] == d)] if d else x.iloc[0:0]
        cand3 = x[(x["foundation_root"] == fr) & (x["date_imaged_yyyymmdd"] == d)] if d else x.iloc[0:0]
        cand4 = x[(x["foundation_root"] == fr) & (x["blob"].str.contains(slug, na=False))] if slug else x.iloc[0:0]

        link_class = ""
        rule = ""
        chosen = x.iloc[0:0]

        if len(cand1) == 1:
            link_class = "class1"
            rule = "datalocation_contains_experiment_folder"
            chosen = cand1
        elif len(cand1) > 1:
            link_class = "class3"
            rule = "datalocation_contains_experiment_folder_ambiguous"
            chosen = cand1
        else:
            if len(cand2) == 1:
                link_class = "class2"
                rule = "date_mount_matches_experiment_date"
                chosen = cand2
            elif len(cand2) > 1:
                link_class = "class3"
                rule = "date_mount_matches_experiment_date_ambiguous"
                chosen = cand2
            else:
                if len(cand3) == 1:
                    link_class = "class2"
                    rule = "date_imaged_matches_experiment_date"
                    chosen = cand3
                elif len(cand3) > 1:
                    link_class = "class3"
                    rule = "date_imaged_matches_experiment_date_ambiguous"
                    chosen = cand3
                else:
                    if len(cand4) == 1:
                        link_class = "class2"
                        rule = "blob_contains_experiment_slug"
                        chosen = cand4
                    elif len(cand4) > 1:
                        link_class = "class3"
                        rule = "blob_contains_experiment_slug_ambiguous"
                        chosen = cand4
                    else:
                        link_class = "class4"
                        rule = "no_candidates"
                        chosen = x.iloc[0:0]

        chosen_excel_row_1based = ""
        if len(chosen) >= 1:
            chosen_excel_row_1based = str(int(chosen.index[0]) + 2)

        rows.append({
            "foundation_root": fr,
            "experiment_folder": ef,
            "experiment_slug": slug,
            "experiment_date": d,
            "link_class": link_class,
            "rule": rule,
            "n_candidates_class1": int(len(cand1)),
            "n_candidates_date_mount": int(len(cand2)),
            "n_candidates_date_imaged": int(len(cand3)),
            "n_candidates_slug_blob": int(len(cand4)),
            "chosen_excel_row_1based": chosen_excel_row_1based,
        })

        if link_class == "class3":
            for excel_idx, xr in chosen.head(50).iterrows():
                cand_rows.append({
                    "foundation_root": fr,
                    "experiment_folder": ef,
                    "experiment_slug": slug,
                    "experiment_date": d,
                    "rule": rule,
                    "excel_row_1based": int(excel_idx) + 2,
                    "date_mount": xr.get("date_mount"),
                    "date_imaged": xr.get("Date imaged"),
                    "mom_parent_cell": xr.get("ZF female genotype"),
                    "dad_parent_cell": xr.get("ZF male genotype"),
                    "inj_plasmids_cell": xr.get("additional plasmids injected"),
                    "inj_rna_cell": xr.get("additional mRNAs injected"),
                    "inj_dye_cell": xr.get("additonal dye and chemicals"),
                    "Data location": xr.get("Data location"),
                })

    out = pd.DataFrame(rows)
    out.to_csv(OUT_LINK, sep="\t", index=False)

    cand_out = pd.DataFrame(cand_rows)
    cand_out.to_csv(OUT_CAND, sep="\t", index=False)

    qc = out["link_class"].value_counts().rename_axis("link_class").reset_index(name="experiments")
    qc.to_csv(OUT_QC, sep="\t", index=False)

    print(f"[OK] wrote {OUT_LINK}")
    print(f"[OK] wrote {OUT_CAND}")
    print(f"[OK] wrote {OUT_QC}")

if __name__ == "__main__":
    main()
