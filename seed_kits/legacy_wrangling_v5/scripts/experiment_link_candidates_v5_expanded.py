from __future__ import annotations

from pathlib import Path
import re
import pandas as pd

ROOT = Path("~/Projects/carp_v2/seed_kits/legacy_wrangling_v5").expanduser()
RAW = ROOT / "raw"
WORKING = ROOT / "working"

IN_XLSX = RAW / "2025-12-22-161955-Cell Observatory - Zebrafish Development.xlsx"
SHEET = "Master Imaging list"
IN_SLUGS = WORKING / "roi_path_slugs_v5.csv"
IN_COV = ROOT / "qc_runs/roi_path_to_markers_pass12_v5.qc_coverage_by_experiment.tsv"

OUT = WORKING / "experiment_link_candidates_v5_expanded.tsv"

RE_DATE8 = re.compile(r"^(\d{8})")

def norm_path(s: str) -> str:
    return str(s).strip().replace("\\", "/")

def parse_date_from_experiment_folder(s: str) -> str:
    m = RE_DATE8.match(str(s))
    return m.group(1) if m else ""

def date_to_yyyymmdd(v) -> str:
    ts = pd.to_datetime(v, errors="coerce")
    if pd.isna(ts):
        return ""
    return ts.strftime("%Y%m%d")

def main() -> None:
    x = pd.read_excel(IN_XLSX, sheet_name=SHEET)

    # Ensure optional columns exist
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
    x["date_mount_yyyymmdd"] = x["date_mount"].map(date_to_yyyymmdd)
    x["date_imaged_yyyymmdd"] = x["Date imaged"].map(date_to_yyyymmdd)
    x["blob"] = x[["Data_location_norm", "free_text_label", "comments"]].astype(str).agg(" | ".join, axis=1)

    slugs = pd.read_csv(IN_SLUGS)
    exp = slugs.drop_duplicates(subset=["foundation_root", "experiment_folder"])[
        ["foundation_root", "experiment_folder", "experiment_slug"]
    ].copy()
    exp["experiment_date"] = exp["experiment_folder"].map(parse_date_from_experiment_folder)

    cov = pd.read_csv(IN_COV, sep="\t")
    exp = exp.merge(cov[["foundation_root","experiment_folder","has_meta"]], on=["foundation_root","experiment_folder"], how="left")
    exp["has_meta"] = exp["has_meta"].fillna(0).astype(int)

    missing = exp[exp["has_meta"] == 0].copy()

    rows = []
    for _, r in missing.iterrows():
        fr = r["foundation_root"]
        ef = r["experiment_folder"]
        slug = str(r["experiment_slug"] or "").strip()
        d = r["experiment_date"]

        # Candidate sets
        cand1 = x[(x["foundation_root"] == fr) & (x["Data_location_norm"].str.contains(ef, na=False))]
        cand2 = x[(x["foundation_root"] == fr) & (x["date_mount_yyyymmdd"] == d)] if d else x.iloc[0:0]
        cand3 = x[(x["foundation_root"] == fr) & (x["date_imaged_yyyymmdd"] == d)] if d else x.iloc[0:0]
        cand4 = x[(x["foundation_root"] == fr) & (x["blob"].str.contains(slug, na=False))] if slug else x.iloc[0:0]

        candidates = [
            ("rule1_datalocation_contains_experiment_folder", cand1),
            ("rule2_date_mount_matches_experiment_date", cand2),
            ("rule3_date_imaged_matches_experiment_date", cand3),
            ("rule4_blob_contains_experiment_slug", cand4),
        ]

        # Pick first non-empty rule as "chosen" but still output all candidates under that rule
        chosen_rule = ""
        chosen = x.iloc[0:0]
        for rule, cand in candidates:
            if len(cand) > 0:
                chosen_rule = rule
                chosen = cand
                break

        # Emit one row per candidate under the chosen rule (up to 50)
        for excel_idx, xr in chosen.head(50).iterrows():
            rows.append({
                "foundation_root": fr,
                "experiment_folder": ef,
                "experiment_slug": slug,
                "experiment_date": d,
                "rule_chosen": chosen_rule,
                "n_candidates_rule1": int(len(cand1)),
                "n_candidates_rule2": int(len(cand2)),
                "n_candidates_rule3": int(len(cand3)),
                "n_candidates_rule4": int(len(cand4)),
                "excel_row_number_1based": int(excel_idx) + 2,  # +2 to approximate Excel row (header + 1-based)
                "date_mount": xr.get("date_mount"),
                "date_imaged": xr.get("Date imaged"),
                "mom_parent_cell": xr.get("ZF female genotype"),
                "dad_parent_cell": xr.get("ZF male genotype"),
                "inj_plasmids_cell": xr.get("additional plasmids injected"),
                "inj_rna_cell": xr.get("additional mRNAs injected"),
                "inj_dye_cell": xr.get("additonal dye and chemicals"),
                "Data location": xr.get("Data location"),
            })

        # If no candidates at all, still emit a stub row
        if len(chosen) == 0:
            rows.append({
                "foundation_root": fr,
                "experiment_folder": ef,
                "experiment_slug": slug,
                "experiment_date": d,
                "rule_chosen": "",
                "n_candidates_rule1": int(len(cand1)),
                "n_candidates_rule2": int(len(cand2)),
                "n_candidates_rule3": int(len(cand3)),
                "n_candidates_rule4": int(len(cand4)),
                "excel_row_number_1based": "",
                "date_mount": "",
                "date_imaged": "",
                "mom_parent_cell": "",
                "dad_parent_cell": "",
                "inj_plasmids_cell": "",
                "inj_rna_cell": "",
                "inj_dye_cell": "",
                "Data location": "",
            })

    out = pd.DataFrame(rows)
    out.to_csv(OUT, sep="\t", index=False)
    print(f"[OK] wrote {OUT} rows={len(out)}")

if __name__ == "__main__":
    main()
