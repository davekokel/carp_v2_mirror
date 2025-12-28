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

OUT = WORKING / "experiment_link_candidates_v5.csv"

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
    for c in ["Data location", "date_mount", "Date imaged", "free_text_label", "comments"]:
        if c not in x.columns:
            x[c] = ""

    x = x.copy()
    x["Data_location_norm"] = x["Data location"].astype(str).map(norm_path)
    x["foundation_root"] = x["Data_location_norm"].str.extract(r"(Aang_Foundation|Korra_Foundation)")[0].fillna("")
    x["date_mount_yyyymmdd"] = x["date_mount"].map(date_to_yyyymmdd)
    x["date_imaged_yyyymmdd"] = x["Date imaged"].map(date_to_yyyymmdd)
    x["blob"] = x[["Data_location_norm", "free_text_label", "comments"]].astype(str).agg(" | ".join, axis=1)

    slugs = pd.read_csv(IN_SLUGS)
    # experiment-level unique mapping
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

        cand1 = x[(x["foundation_root"] == fr) & (x["Data_location_norm"].str.contains(ef, na=False))]
        rule1 = f"datalocation_contains_experiment_folder"

        cand2 = x[(x["foundation_root"] == fr) & (x["date_mount_yyyymmdd"] == d)] if d else x.iloc[0:0]
        rule2 = "date_mount_matches_experiment_date"

        cand3 = x[(x["foundation_root"] == fr) & (x["date_imaged_yyyymmdd"] == d)] if d else x.iloc[0:0]
        rule3 = "date_imaged_matches_experiment_date"

        cand4 = x[(x["foundation_root"] == fr) & (x["blob"].str.contains(slug, na=False))] if slug else x.iloc[0:0]
        rule4 = "blob_contains_experiment_slug"

        candidates = [
            (rule1, cand1),
            (rule2, cand2),
            (rule3, cand3),
            (rule4, cand4),
        ]

        # choose the first rule that yields any candidates, but report all counts
        chosen_rule = ""
        chosen = x.iloc[0:0]
        for rule, cand in candidates:
            if len(cand) > 0:
                chosen_rule = rule
                chosen = cand
                break

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
            "candidate_excel_row_indices": ";".join(map(str, chosen.index.tolist()[:50])),
            "candidate_data_locations_sample": " || ".join(chosen["Data location"].astype(str).head(5).tolist()),
        })

    out = pd.DataFrame(rows).sort_values(["foundation_root","experiment_folder"])
    out.to_csv(OUT, index=False)
    print(f"[OK] wrote {OUT} rows={len(out)}")

if __name__ == "__main__":
    main()
