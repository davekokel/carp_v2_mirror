from __future__ import annotations

from pathlib import Path
import pandas as pd
import re

ROOT = Path("~/Projects/carp_v2/seed_kits/legacy_wrangling_v5").expanduser()
WORKING = ROOT / "working"
QC = ROOT / "qc_runs"

IN_ROI_SLUGS = WORKING / "roi_path_slugs_v5.csv"
IN_XLSX = WORKING / "master_imaging_list_mountid_filled_v5.xlsx"
SHEET = "Master Imaging list"

OUT = WORKING / "roi_path_to_date_mount_id_step1_v5.csv"
OUT_QC = QC / "roi_path_to_date_mount_id_step1_v5.qc.tsv"

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

def build_date_mount_id(date_mount, mount_id) -> str:
    dm = pd.to_datetime(date_mount, errors="coerce")
    mid = _s(mount_id)
    if pd.notna(dm) and mid:
        return dm.strftime("%Y-%m-%d") + "__" + mid
    return ""

def main() -> None:
    WORKING.mkdir(parents=True, exist_ok=True)
    QC.mkdir(parents=True, exist_ok=True)

    roi = pd.read_csv(IN_ROI_SLUGS)[["roi_path","foundation_root","experiment_folder"]].copy()
    roi["experiment_date"] = roi["experiment_folder"].map(exp_date_from_folder)

    x = pd.read_excel(IN_XLSX, sheet_name=SHEET)
    for c in ["Data location","date_mount","mount_id"]:
        if c not in x.columns:
            raise SystemExit(f"[STOP] missing column in filled sheet: {c}")

    x = x.copy()
    x["dl"] = x["Data location"].astype(str).map(norm_path)
    x["fr"] = x["dl"].str.extract(r"(Aang_Foundation|Korra_Foundation)")[0].fillna("")
    x["date_mount_id"] = [build_date_mount_id(a,b) for a,b in zip(x["date_mount"], x["mount_id"])]

    out_rows = []
    for _, r in roi.iterrows():
        fr = r["foundation_root"]
        ef = r["experiment_folder"]
        # simplest linkage: data location contains experiment folder
        cand = x[(x["fr"]==fr) & (x["dl"].str.contains(ef, na=False))]
        dmids = sorted(set([_s(v) for v in cand["date_mount_id"].tolist() if _s(v)]))
        out_rows.append({
            "roi_path": r["roi_path"],
            "date_mount_id": dmids[0] if len(dmids)==1 else "",
        })

    out_df = pd.DataFrame(out_rows)
    out_df.to_csv(OUT, index=False)

    qc = {
        "roi_paths_total": int(len(out_df)),
        "roi_with_date_mount_id": int((out_df["date_mount_id"].astype(str).str.len()>0).sum()),
        "roi_missing_date_mount_id": int((out_df["date_mount_id"].astype(str).str.len()==0).sum()),
    }
    pd.DataFrame([qc]).to_csv(OUT_QC, sep="\t", index=False)

    print(f"[OK] wrote {OUT} rows={len(out_df)}")
    print(f"[QC] wrote {OUT_QC}")

if __name__ == "__main__":
    main()
