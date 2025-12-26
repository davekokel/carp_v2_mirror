from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Tuple, Optional
import json

import pandas as pd

RAW = Path("seed_kits/legacy_wrangling_v2/raw")
OUT_JSON = Path("seed_kits/legacy_wrangling_v4/qc/raw_mapping_files_audit_v4.json")
OUT_TSV  = Path("seed_kits/legacy_wrangling_v4/qc/raw_mapping_files_audit_v4.tsv")

FILES = [
    RAW / "2025-11-13-092338-korra_aang_roi_root_tiffs_good-3.xlsx",
    RAW / "2025-11-21-220012-imaging_sheet.xlsx",
    RAW / "experiment_hole_patch_v7.csv",
    RAW / "organelles_manual_mapping_v6.csv",
    RAW / "parent_hole_patch_v6.csv",
    RAW / "plasmids_janelia_googlesheet.xlsx",
    RAW / "roi_missing_parents_for_manual_mapping_DQM_CNH (1).csv",
    RAW / "Unique_injected_plasmid__preview_dqm.xlsx",
    RAW / "Unique_injected_rna__preview_dqm.xlsx",
    RAW / "Unique_parent_names__mom_dad_combined__preview_dqm.xlsx",
]

COMMON_KEY_CANDIDATES = [
    ("roi_dir",),
    ("roi_path",),
    ("roi_dir","slug"),
    ("dataset_slug",),
    ("parent_fish_name",),
    ("mother_fish_manual","father_fish_manual"),
    ("injection type","injection plasmid"),
    ("plasmid_base_code","allele"),
    ("injected_rna",),
    ("injected_plasmid",),
]

def _s(x: object) -> str:
    if x is None:
        return ""
    t = str(x)
    return t.strip()

def _read_csv(p: Path) -> pd.DataFrame:
    return pd.read_csv(p, dtype=str, keep_default_na=False, na_filter=False).fillna("")

def _read_xlsx_sheets(p: Path) -> Dict[str, pd.DataFrame]:
    x = pd.ExcelFile(p)
    out: Dict[str, pd.DataFrame] = {}
    for sh in x.sheet_names:
        df = pd.read_excel(x, sheet_name=sh, dtype=str, keep_default_na=False, na_filter=False).fillna("")
        df.columns = [str(c).strip() for c in df.columns]
        out[sh] = df
    return out

def _best_key(df: pd.DataFrame) -> Optional[Tuple[str,...]]:
    cols = {c for c in df.columns}
    for cand in COMMON_KEY_CANDIDATES:
        if all(c in cols for c in cand):
            return cand
    return None

def _coverage(df: pd.DataFrame, col: str) -> Tuple[int,int]:
    if col not in df.columns:
        return (0, len(df))
    nonblank = int((df[col].astype(str).map(_s) != "").sum())
    return (nonblank, len(df))

def _dupes(df: pd.DataFrame, key: Tuple[str,...]) -> int:
    if not key:
        return 0
    if any(k not in df.columns for k in key):
        return 0
    d = df[list(key)].astype(str).applymap(_s)
    return int(d.duplicated().sum())

def _head3(df: pd.DataFrame) -> List[Dict[str,str]]:
    h = df.head(3).copy()
    for c in h.columns:
        h[c] = h[c].astype(str).map(_s)
    return h.to_dict(orient="records")

def audit_one_df(file_path: Path, sheet: str, df: pd.DataFrame) -> Dict[str, object]:
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]

    key = _best_key(df)
    key_cols = list(key) if key else []

    cov = {}
    for c in key_cols:
        cov[c] = {"nonblank": _coverage(df, c)[0], "n_rows": len(df)}

    extras = {}
    for c in ["roi_dir","roi_path","parent_fish_name","plasmid_base_code","allele","injected_rna","injected_plasmid","zf_female_genotype","zf_male_genotype"]:
        if c in df.columns:
            extras[c] = {"nonblank": _coverage(df, c)[0], "n_rows": len(df)}

    return {
        "source": "xlsx" if file_path.suffix.lower() in (".xlsx", ".xls") else "csv",
        "file": str(file_path),
        "sheet": sheet,
        "n_rows": int(len(df)),
        "n_cols": int(len(df.columns)),
        "columns": list(df.columns),
        "best_key": "|".join(key_cols),
        "dupes_on_best_key": _dupes(df, tuple(key_cols)) if key_cols else 0,
        "coverage_best_key": cov,
        "coverage_common": extras,
        "sample_head3": _head3(df),
    }

def main() -> None:
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)

    records: List[Dict[str, object]] = []
    flat_rows: List[Dict[str, str]] = []

    for p in FILES:
        if not p.exists():
            records.append({"file": str(p), "error": "missing"})
            continue

        suf = p.suffix.lower()
        try:
            if suf in (".csv", ".tsv"):
                df = _read_csv(p)
                df.columns = [str(c).strip() for c in df.columns]
                rec = audit_one_df(p, "", df)
                records.append(rec)
                flat_rows.append({
                    "file": str(p.name),
                    "sheet": "",
                    "n_rows": str(rec["n_rows"]),
                    "n_cols": str(rec["n_cols"]),
                    "best_key": str(rec["best_key"]),
                    "dupes_on_best_key": str(rec["dupes_on_best_key"]),
                    "columns": "|".join(rec["columns"]),
                })
            elif suf in (".xlsx", ".xls"):
                sheets = _read_xlsx_sheets(p)
                for sh, df in sheets.items():
                    rec = audit_one_df(p, sh, df)
                    records.append(rec)
                    flat_rows.append({
                        "file": str(p.name),
                        "sheet": sh,
                        "n_rows": str(rec["n_rows"]),
                        "n_cols": str(rec["n_cols"]),
                        "best_key": str(rec["best_key"]),
                        "dupes_on_best_key": str(rec["dupes_on_best_key"]),
                        "columns": "|".join(rec["columns"]),
                    })
            else:
                records.append({"file": str(p), "error": f"unsupported extension {suf}"})
        except Exception as e:
            records.append({"file": str(p), "error": repr(e)})

    OUT_JSON.write_text(json.dumps(records, indent=2), encoding="utf-8")
    pd.DataFrame(flat_rows).to_csv(OUT_TSV, sep="\t", index=False)

    print(str(OUT_TSV))
    print(str(OUT_JSON))
    print("[QC] records", len(records))

if __name__ == "__main__":
    main()
