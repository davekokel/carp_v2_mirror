from __future__ import annotations

from pathlib import Path
import re
import pandas as pd

ROOT = Path("~/Projects/carp_v2/seed_kits/legacy_wrangling_v5").expanduser()
WORKING = ROOT / "working"
QC = ROOT / "qc_runs"

IN_CSV = WORKING / "roi_path_to_session_markers_v5.csv"

OUT_CSV = WORKING / "roi_path_to_session_markers_v5_step4_defaults.csv"
OUT_QC = QC / "roi_path_to_session_markers_v5_step4_defaults.qc.tsv"
OUT_LOG = QC / "roi_path_to_session_markers_v5_step4_defaults.log.tsv"

def _s(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and pd.isna(v):
        return ""
    return str(v).strip()

def is_blank(v) -> bool:
    t = _s(v)
    return t == "" or t.lower() in ("nan", "none")

# Full-path bucket detection (case-insensitive)
RE_MEM_MITO = re.compile(r"(?i)\bmem[-_]?mito\b")
RE_MEM_HIST = re.compile(r"(?i)\bmem[-_]?histone\b")
RE_SKITTLES = re.compile(r"(?i)\bskittl(?:es|ez)\b")

def detect_bucket(roi_path: str) -> str:
    s = str(roi_path)
    if RE_MEM_MITO.search(s):
        return "mem_mito"
    if RE_MEM_HIST.search(s):
        return "mem_histone"
    if RE_SKITTLES.search(s):
        return "skittles"
    return ""

# Defaults you requested
DEFAULTS = {
    "mem_mito":    ("pDQM082;pDQM136", "315;325"),
    "mem_histone": ("pDQM005;pDQM133", "301;324"),
    "skittles":    ("pDQM034",         "309"),
}

def main() -> None:
    WORKING.mkdir(parents=True, exist_ok=True)
    QC.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(IN_CSV)

    need = {
        "roi_path",
        "date_mount_id",
        "genotype_base_codes",
        "genotype_allele_codes",
        "treatment_rna_base_codes",
        "treatment_plasmid_base_codes",
    }
    missing = sorted(list(need - set(df.columns)))
    if missing:
        raise SystemExit(f"[STOP] input missing columns: {missing}")

    df = df.copy()
    df["bucket"] = df["roi_path"].map(detect_bucket)

    logs = []
    filled = 0

    for i, r in df.iterrows():
        if not is_blank(r.get("genotype_base_codes")):
            continue

        bucket = _s(r.get("bucket"))
        if bucket not in DEFAULTS:
            continue

        geno_bc, geno_al = DEFAULTS[bucket]
        df.at[i, "genotype_base_codes"] = geno_bc
        df.at[i, "genotype_allele_codes"] = geno_al

        logs.append({
            "roi_path": _s(r.get("roi_path")),
            "date_mount_id": _s(r.get("date_mount_id")),
            "bucket": bucket,
            "set_genotype_base_codes": geno_bc,
            "set_genotype_allele_codes": geno_al,
        })
        filled += 1

    df[[
        "roi_path",
        "date_mount_id",
        "genotype_base_codes",
        "genotype_allele_codes",
        "treatment_rna_base_codes",
        "treatment_plasmid_base_codes",
    ]].to_csv(OUT_CSV, index=False)

    pd.DataFrame([{
        "rows_total": int(len(df)),
        "rows_filled_by_step4_defaults": int(filled),
    }]).to_csv(OUT_QC, sep="\t", index=False)

    pd.DataFrame(logs).to_csv(OUT_LOG, sep="\t", index=False)

    print(f"[OK] wrote {OUT_CSV} rows={len(df)} filled={filled}")
    print(f"[QC] wrote {OUT_QC}")
    print(f"[QC] wrote {OUT_LOG}")

if __name__ == "__main__":
    main()
