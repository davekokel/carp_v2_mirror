from __future__ import annotations

from pathlib import Path
import pandas as pd
import re

ROOT = Path("~/Projects/carp_v2/seed_kits/legacy_wrangling_v5").expanduser()
RAW = ROOT / "raw"
WORKING = ROOT / "working"
QC = ROOT / "qc_runs"

IN_ROI_SLUGS = WORKING / "roi_path_slugs_v5.csv"
IN_XLSX = RAW / "2025-12-22-161955-Cell Observatory - Zebrafish Development.xlsx"
SHEET = "Master Imaging list"

OUT = WORKING / "roi_path_to_date_mount_id_step1_v5.csv"
QC_SUMMARY = QC / "roi_path_to_date_mount_id_step1_v5.qc.tsv"
QC_MISSING = QC / "roi_path_to_date_mount_id_step1_v5.qc_missing.tsv"
QC_AMBIG = QC / "roi_path_to_date_mount_id_step1_v5.qc_ambiguous.tsv"

RE_DATE8 = re.compile(r"^(\d{8})")

def _s(v) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    return str(v).strip()

def norm_path(s: str) -> str:
    return str(s).strip().replace("\\", "/")

def exp_date_from_folder(folder: str) -> str:
    m = RE_DATE8.match(str(folder))
    return m.group(1) if m else ""

def to_dt(v):
    return pd.to_datetime(v, errors="coerce")

def build_date_mount_id(date_mount, mount_id) -> str:
    dm = pd.to_datetime(date_mount, errors="coerce")
    mid = _s(mount_id)
    if pd.notna(dm) and mid:
        return dm.strftime("%Y-%m-%d") + "__" + mid
    return ""

def main() -> None:
    for p in (IN_ROI_SLUGS, IN_XLSX):
        if not p.exists():
            raise SystemExit(f"[STOP] missing input: {p}")

    WORKING.mkdir(parents=True, exist_ok=True)
    QC.mkdir(parents=True, exist_ok=True)

    roi = pd.read_csv(IN_ROI_SLUGS)[["roi_path","foundation_root","experiment_folder"]].copy()
    roi["experiment_date"] = roi["experiment_folder"].map(exp_date_from_folder)

    x = pd.read_excel(IN_XLSX, sheet_name=SHEET)

    # required columns for session identity
    for c in ["Data location", "date_mount", "mount_id", "Date imaged"]:
        if c not in x.columns:
            raise SystemExit(f"[STOP] Master Imaging list missing column: {c}")

    x = x.copy()
    x["Data_location_norm"] = x["Data location"].astype(str).map(norm_path)
    x["foundation_root"] = x["Data_location_norm"].str.extract(r"(Aang_Foundation|Korra_Foundation)")[0].fillna("")
    x["date_mount_dt"] = x["date_mount"].map(to_dt)
    x["date_imaged_dt"] = x["Date imaged"].map(to_dt)
    x["date_mount_id"] = [build_date_mount_id(a,b) for a,b in zip(x["date_mount"], x["mount_id"])]

    out_rows = []
    missing_rows = []
    ambig_rows = []

    for _, r in roi.iterrows():
        roi_path = r["roi_path"]
        fr = r["foundation_root"]
        ef = r["experiment_folder"]
        exp_date = _s(r["experiment_date"])

        # Primary (textbook) linkage: Data location contains experiment_folder under the same foundation root
        cand = x[(x["foundation_root"] == fr) & (x["Data_location_norm"].str.contains(ef, na=False))].copy()

        # If none, fall back to date_mount == experiment_date within foundation root
        rule = "datalocation_contains_experiment_folder"
        if len(cand) == 0 and exp_date:
            rule = "date_mount_matches_experiment_date"
            exp_dt = pd.to_datetime(exp_date, format="%Y%m%d", errors="coerce")
            if pd.notna(exp_dt):
                cand = x[(x["foundation_root"] == fr) & (x["date_mount_dt"].dt.date == exp_dt.date())].copy()

        # If still none, fall back to date_imaged == experiment_date within foundation root
        if len(cand) == 0 and exp_date:
            rule = "date_imaged_matches_experiment_date"
            exp_dt = pd.to_datetime(exp_date, format="%Y%m%d", errors="coerce")
            if pd.notna(exp_dt):
                cand = x[(x["foundation_root"] == fr) & (x["date_imaged_dt"].dt.date == exp_dt.date())].copy()

        if len(cand) == 0:
            out_rows.append({"roi_path": roi_path, "date_mount_id": ""})
            missing_rows.append({
                "roi_path": roi_path,
                "foundation_root": fr,
                "experiment_folder": ef,
                "experiment_date": exp_date,
                "reason": "no_candidates",
            })
            continue

        # Prefer candidates that actually have date_mount_id populated
        cand2 = cand[cand["date_mount_id"].astype(str).str.len() > 0].copy()
        if len(cand2) == 1:
            out_rows.append({"roi_path": roi_path, "date_mount_id": cand2.iloc[0]["date_mount_id"]})
            continue
        if len(cand2) > 1:
            # ambiguous even among session-identified rows
            out_rows.append({"roi_path": roi_path, "date_mount_id": ""})
            ambig_rows.append({
                "roi_path": roi_path,
                "foundation_root": fr,
                "experiment_folder": ef,
                "rule": rule,
                "n_candidates": int(len(cand2)),
                "date_mount_id_samples": " || ".join(sorted(set(cand2["date_mount_id"].astype(str).tolist()))[:10]),
                "data_location_samples": " || ".join(cand2["Data location"].astype(str).head(5).tolist()),
            })
            continue

        # candidates exist but none have date_mount_id (mount_id/date_mount missing in sheet)
        out_rows.append({"roi_path": roi_path, "date_mount_id": ""})
        missing_rows.append({
            "roi_path": roi_path,
            "foundation_root": fr,
            "experiment_folder": ef,
            "experiment_date": exp_date,
            "reason": f"{rule}:candidates_but_missing_date_mount_or_mount_id",
            "data_location_samples": " || ".join(cand["Data location"].astype(str).head(5).tolist()),
        })

    out_df = pd.DataFrame(out_rows)
    out_df.to_csv(OUT, index=False)

    qc = {
        "roi_paths_total": int(len(out_df)),
        "roi_with_date_mount_id": int((out_df["date_mount_id"].astype(str).str.len() > 0).sum()),
        "roi_missing_date_mount_id": int((out_df["date_mount_id"].astype(str).str.len() == 0).sum()),
        "missing_rows_logged": int(len(missing_rows)),
        "ambiguous_rows_logged": int(len(ambig_rows)),
    }
    pd.DataFrame([qc]).to_csv(QC_SUMMARY, sep="\t", index=False)
    pd.DataFrame(missing_rows).to_csv(QC_MISSING, sep="\t", index=False)
    pd.DataFrame(ambig_rows).to_csv(QC_AMBIG, sep="\t", index=False)

    print(f"[OK] wrote {OUT} rows={len(out_df)}")
    print(f"[QC] wrote {QC_SUMMARY}")
    print(f"[QC] wrote {QC_MISSING}")
    print(f"[QC] wrote {QC_AMBIG}")

if __name__ == "__main__":
    main()
