from __future__ import annotations

from pathlib import Path
import re
import pandas as pd

def normalize_date_key(v):
    if v is None:
        return None
    # pandas often gives 20250721.0 as float
    try:
        if isinstance(v, float):
            if pd.isna(v):
                return None
            iv = int(v)
            s = str(iv)
            return s if len(s) == 8 else None
        if isinstance(v, int):
            s = str(v)
            return s if len(s) == 8 else None
    except Exception:
        pass

    s = str(v).strip()
    if s.lower() in ("nan", "none", ""):
        return None
    # handle "20250721.0"
    if s.endswith(".0"):
        s = s[:-2]
    # keep only first 8 digits if it starts with them
    m = re.match(r"^(20\d{6})", s)
    if m:
        return m.group(1)
    return None

REPO_ROOT = Path(__file__).resolve().parents[3]
WORK = REPO_ROOT / "seed_kits" / "legacy_wrangling_v3" / "working"
RAW  = REPO_ROOT / "seed_kits" / "legacy_wrangling_v2" / "raw"

IN_LINK = WORK / "output_from_linking_v5.csv"
IN_IMAGING_XLSX = RAW / "2025-11-21-220012-imaging_sheet.xlsx"

OUT_INFERRED = WORK / "imaging_sheet_inferred_rows.csv"
OUT_AUGMENTED = WORK / "imaging_sheet_augmented_v3.csv"
OUT_SKIPPED = WORK / "imaging_sheet_inferred_rows_skipped.csv"

def nonempty(x) -> bool:
    if x is None:
        return False
    if isinstance(x, float) and pd.isna(x):
        return False
    s = str(x).strip()
    return s != "" and s.lower() not in ("nan", "none", "na", "n/a")

def foundation_from_roi_dir(roi_dir: str) -> str | None:
    if not nonempty(roi_dir):
        return None
    s = str(roi_dir)
    if "/Aang_Foundation/" in s:
        return "aang"
    if "/Korra_Foundation/" in s:
        return "korra"
    return None

def experiment_folder_from_roi_dir(roi_dir: str) -> str | None:
    if not nonempty(roi_dir):
        return None
    s = str(roi_dir)
    m = re.search(r"/(Aang_Foundation|Korra_Foundation)/([^/]+)", s)
    return m.group(2) if m else None

def yyyymmdd_from_experiment_folder(folder: str) -> str | None:
    if not nonempty(folder):
        return None
    m = re.match(r"^(20\d{6})[_-]", str(folder))
    return m.group(1) if m else None

def windows_data_location(foundation: str, experiment_folder: str) -> str:
    if foundation == "aang":
        return f"X:\\abcabc\\Aang_Foundation\\{experiment_folder}"
    if foundation == "korra":
        return f"X:\\abcabc\\Korra_Foundation\\{experiment_folder}"
    return f"X:\\abcabc\\{experiment_folder}"

def main() -> None:
    if not IN_LINK.exists():
        raise SystemExit(f"missing: {IN_LINK}")
    if not IN_IMAGING_XLSX.exists():
        raise SystemExit(f"missing: {IN_IMAGING_XLSX}")

    link = pd.read_csv(IN_LINK, low_memory=False)
    img = pd.read_excel(IN_IMAGING_XLSX)

    need = ["roi_dir", "link_source"]
    for c in need:
        if c not in link.columns:
            raise SystemExit(f"02_infer: link CSV missing required col: {c}")

    unmatched = link[link["link_source"].astype(str).str.strip().eq("unmatched")].copy()
    unmatched["foundation"] = unmatched["roi_dir"].astype(str).apply(foundation_from_roi_dir)
    unmatched["experiment_folder"] = unmatched["roi_dir"].astype(str).apply(experiment_folder_from_roi_dir)
    unmatched["date_key"] = unmatched.get("date_key", pd.Series([pd.NA] * len(unmatched)))

    rows = []
    skipped = []

    for (foundation, exp_folder), grp in unmatched.groupby(["foundation", "experiment_folder"], dropna=False):
        if not nonempty(foundation) or not nonempty(exp_folder):
            skipped.append({
                "reason": "missing foundation/experiment_folder",
                "foundation": foundation,
                "experiment_folder": exp_folder,
                "n_rois": len(grp),
                "sample_roi_dir": grp["roi_dir"].astype(str).head(1).iloc[0],
            })
            continue

        date_key = None
        vals = grp.get("date_key", pd.Series([], dtype="object")).dropna().astype(str).str.strip()
        vals = vals[vals.ne("") & vals.ne("nan") & vals.ne("None")]
        if len(vals):
            date_key = vals.value_counts().index[0]
            date_key = normalize_date_key(date_key)

        if not nonempty(date_key):
            date_key = yyyymmdd_from_experiment_folder(exp_folder)
            date_key = normalize_date_key(date_key)
        if not nonempty(date_key):
            skipped.append({
                "reason": "missing date_key",
                "foundation": foundation,
                "experiment_folder": exp_folder,
                "n_rois": len(grp),
                "sample_roi_dir": grp["roi_dir"].astype(str).head(1).iloc[0],
            })
            continue

        date_key = normalize_date_key(date_key)
        dt_mount = pd.to_datetime(date_key, format="%Y%m%d", errors="coerce")
        if pd.isna(dt_mount):
            skipped.append({
                "reason": "unparseable date_key",
                "foundation": foundation,
                "experiment_folder": exp_folder,
                "date_key": date_key,
                "n_rois": len(grp),
                "sample_roi_dir": grp["roi_dir"].astype(str).head(1).iloc[0],
            })
            continue

        rows.append({
            "date_mount": dt_mount.date().isoformat(),
            "mount_id": pd.NA,
            "Date imaged": dt_mount.date().isoformat(),
            "Data location": windows_data_location(foundation, exp_folder),
            "ZF female genotype": pd.NA,
            "ZF male genotype": pd.NA,
            "additional plasmids injected": pd.NA,
            "additional mRNAs injected": pd.NA,
            "additonal proteins injected": pd.NA,
            "additonal dye and chemicals": pd.NA,
            "Date born": pd.NA,
            "Time mounted": pd.NA,
            "Mounting Orientation": pd.NA,
            "Date screened/Initial feedback": pd.NA,
            "Time placed in scope": pd.NA,
            "Start of imaging time": pd.NA,
            "End of imaging time": pd.NA,
            "Imaged Locations": pd.NA,
            "Unique Targets with blanks": pd.NA,
            "Unique Targets": pd.NA,
            "Dataset size (GB) - raw data only": pd.NA,
            "Camera Filters": pd.NA,
            "JSON excite map for ZF male": pd.NA,
            "JSON excite map for ZF female": pd.NA,
            "JSON excite map for plasmid": pd.NA,
            "JSON excite map for mRNA": pd.NA,
            "comments": pd.NA,
            "Data evaluation comments": pd.NA,
            "inferred_row": True,
            "inferred_foundation": foundation,
            "inferred_experiment_folder": exp_folder,
            "inferred_date_key": date_key,
            "inferred_n_rois": len(grp),
        })

    inferred = pd.DataFrame(rows)
    skipped_df = pd.DataFrame(skipped)

    WORK.mkdir(parents=True, exist_ok=True)
    inferred.to_csv(OUT_INFERRED, index=False)
    skipped_df.to_csv(OUT_SKIPPED, index=False)

    img2 = img.copy()
    img2["inferred_row"] = False
    for c in inferred.columns:
        if c not in img2.columns:
            img2[c] = pd.NA
    for c in img2.columns:
        if c not in inferred.columns:
            inferred[c] = pd.NA

    augmented = pd.concat([img2, inferred[img2.columns]], ignore_index=True)
    augmented.to_csv(OUT_AUGMENTED, index=False)

    print("IN_LINK", IN_LINK)
    print("N_UNMATCHED_ROIS", len(unmatched))
    print("OUT_INFERRED", OUT_INFERRED, "ROWS", len(inferred))
    print("OUT_SKIPPED", OUT_SKIPPED, "ROWS", len(skipped_df))
    print("OUT_AUGMENTED", OUT_AUGMENTED, "ROWS", len(augmented))

if __name__ == "__main__":
    main()
