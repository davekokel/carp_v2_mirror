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

OUT = WORKING / "experiment_link_resolution_pass4.tsv"

RE_DATE8 = re.compile(r"^(\d{8})")

def norm_path(s: str) -> str:
    return str(s).strip().replace("\\", "/")

def exp_date_from_folder(folder: str):
    m = RE_DATE8.match(str(folder))
    if not m:
        return pd.NaT
    return pd.to_datetime(m.group(1), format="%Y%m%d", errors="coerce")

def to_dt(v):
    return pd.to_datetime(v, errors="coerce")

def sig_row(r) -> tuple[str,str,str,str,str]:
    return (
        str(r.get("ZF female genotype") or "").strip(),
        str(r.get("ZF male genotype") or "").strip(),
        str(r.get("additional plasmids injected") or "").strip(),
        str(r.get("additional mRNAs injected") or "").strip(),
        str(r.get("additonal dye and chemicals") or "").strip(),
    )

def main() -> None:
    x = pd.read_excel(IN_XLSX, sheet_name=SHEET)
    for c in [
        "Data location","date_mount","Date imaged",
        "ZF female genotype","ZF male genotype",
        "additional plasmids injected","additional mRNAs injected","additonal dye and chemicals",
        "free_text_label","comments",
    ]:
        if c not in x.columns:
            x[c] = ""

    x = x.copy()
    x["Data_location_norm"] = x["Data location"].astype(str).map(norm_path)
    x["foundation_root"] = x["Data_location_norm"].str.extract(r"(Aang_Foundation|Korra_Foundation)")[0].fillna("")
    x["date_mount_dt"] = x["date_mount"].map(to_dt)
    x["date_imaged_dt"] = x["Date imaged"].map(to_dt)

    slugs = pd.read_csv(IN_SLUGS)
    exp = slugs.drop_duplicates(subset=["foundation_root","experiment_folder"])[["foundation_root","experiment_folder","experiment_slug"]].copy()

    cov = pd.read_csv(IN_COV, sep="\t")
    exp = exp.merge(cov[["foundation_root","experiment_folder","has_meta"]], on=["foundation_root","experiment_folder"], how="left")
    exp["has_meta"] = exp["has_meta"].fillna(0).astype(int)

    missing = exp[exp["has_meta"]==0].copy()
    missing["exp_date_dt"] = missing["experiment_folder"].map(exp_date_from_folder)

    rows = []
    for _, e in missing.iterrows():
        fr = e["foundation_root"]
        ef = e["experiment_folder"]
        slug = str(e.get("experiment_slug") or "").strip()
        exp_dt = e["exp_date_dt"]

        # candidate set: prefer datalocation contains experiment_folder; else fall back to same-day mount or imaged; else slug in text blob
        cand = x[(x["foundation_root"]==fr) & (x["Data_location_norm"].str.contains(ef, na=False))]
        cand_rule = "datalocation_contains_experiment_folder"

        if len(cand)==0 and pd.notna(exp_dt):
            cand = x[(x["foundation_root"]==fr) & (x["date_mount_dt"].dt.date == exp_dt.date())]
            cand_rule = "date_mount_eq_exp_date"

        if len(cand)==0 and pd.notna(exp_dt):
            cand = x[(x["foundation_root"]==fr) & (x["date_imaged_dt"].dt.date == exp_dt.date())]
            cand_rule = "date_imaged_eq_exp_date"

        if len(cand)==0 and slug:
            blob = x[["Data_location_norm","free_text_label","comments"]].astype(str).agg(" | ".join, axis=1)
            cand = x[(x["foundation_root"]==fr) & (blob.str.contains(slug, na=False))]
            cand_rule = "blob_contains_experiment_slug"

        if len(cand)==0:
            rows.append({
                "foundation_root": fr,
                "experiment_folder": ef,
                "experiment_slug": slug,
                "cand_rule": cand_rule,
                "n_candidates": 0,
                "chosen_method": "none",
                "chosen_excel_row_1based": "",
                "chosen_sig_count": "",
                "chosen_time_delta_days": "",
                "mom_parent_cell": "",
                "dad_parent_cell": "",
                "inj_plasmids_cell": "",
                "inj_rna_cell": "",
                "inj_dye_cell": "",
                "Data location": "",
            })
            continue

        # Compute signatures + mode
        cand = cand.copy()
        cand["sig"] = cand.apply(sig_row, axis=1)
        vc = cand["sig"].value_counts()
        top_n = int(vc.iloc[0])
        top_sigs = vc[vc == top_n].index.tolist()

        chosen = None
        chosen_method = ""
        chosen_sig_count = ""
        chosen_delta = ""

        if len(top_sigs) == 1:
            # unique mode
            sig = top_sigs[0]
            chosen = cand[cand["sig"] == sig].iloc[0]
            chosen_method = "mode"
            chosen_sig_count = str(top_n)
        else:
            # tie -> closest in time (mount preferred, else imaged)
            if pd.notna(exp_dt):
                def delta_days(r):
                    dm = r["date_mount_dt"]
                    di = r["date_imaged_dt"]
                    if pd.notna(dm):
                        return abs((dm.normalize() - exp_dt.normalize()).days)
                    if pd.notna(di):
                        return abs((di.normalize() - exp_dt.normalize()).days)
                    return 10**9
                cand["delta_days"] = cand.apply(delta_days, axis=1)
                min_d = int(cand["delta_days"].min())
                best = cand[cand["delta_days"] == min_d]
                if len(best) == 1:
                    chosen = best.iloc[0]
                    chosen_method = "closest_time"
                    chosen_delta = str(min_d)
                else:
                    # still tied
                    chosen = best.iloc[0]
                    chosen_method = "ambiguous_tie"
                    chosen_delta = str(min_d)
            else:
                chosen = cand.iloc[0]
                chosen_method = "ambiguous_no_date"

        rows.append({
            "foundation_root": fr,
            "experiment_folder": ef,
            "experiment_slug": slug,
            "cand_rule": cand_rule,
            "n_candidates": int(len(cand)),
            "chosen_method": chosen_method,
            "chosen_excel_row_1based": int(chosen.name) + 2,
            "chosen_sig_count": chosen_sig_count,
            "chosen_time_delta_days": chosen_delta,
            "mom_parent_cell": chosen.get("ZF female genotype"),
            "dad_parent_cell": chosen.get("ZF male genotype"),
            "inj_plasmids_cell": chosen.get("additional plasmids injected"),
            "inj_rna_cell": chosen.get("additional mRNAs injected"),
            "inj_dye_cell": chosen.get("additonal dye and chemicals"),
            "Data location": chosen.get("Data location"),
        })

    out = pd.DataFrame(rows)
    out.to_csv(OUT, sep="\t", index=False)
    print(f"[OK] wrote {OUT} rows={len(out)}")

if __name__ == "__main__":
    main()
