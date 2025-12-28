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

RE_DATE8 = re.compile(r"^(\d{8})[_-]?")

def _s(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and pd.isna(v):
        return ""
    return str(v).strip()

def is_blank(v) -> bool:
    t = _s(v)
    return t == "" or t.lower() in ("nan", "none")

def experiment_slug_from_roi_path(roi_path: str) -> str:
    parts = [p for p in str(roi_path).strip("/").split("/") if p]
    if len(parts) < 2:
        return ""
    folder = parts[1]
    return RE_DATE8.sub("", str(folder))

def main() -> None:
    WORKING.mkdir(parents=True, exist_ok=True)
    QC.mkdir(parents=True, exist_ok=True)

    if not IN_CSV.exists():
        raise SystemExit(f"[STOP] missing input: {IN_CSV}")

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
    df["experiment_slug"] = df["roi_path"].map(experiment_slug_from_roi_path).fillna("")

    # Domain-default rules (only applied when genotype_base_codes is blank)
    # NOTE: These are explicit defaults, stamped in QC log.
    RULES = [
        ("mem_mito",      re.compile(r"(?i)\bmem[-_]?mito\b"),      "pDQM082;pDQM136", "315;325"),
        ("mem_histone",   re.compile(r"(?i)\bmem[-_]?histone\b"),   "pDQM005;pDQM133", "301;324"),
        ("skittles",      re.compile(r"(?i)\bskittl(?:es|ez)\b"),   "pDQM034",         "309"),
    ]

    filled = 0
    logs = []

    for i, r in df.iterrows():
        if not is_blank(r.get("genotype_base_codes")):
            continue

        slug = _s(r.get("experiment_slug"))
        roi_path = _s(r.get("roi_path"))
        date_mount_id = _s(r.get("date_mount_id"))

        applied = False
        for rule_name, rule_re, geno_bc, geno_al in RULES:
            if rule_re.search(slug):
                df.at[i, "genotype_base_codes"] = geno_bc
                df.at[i, "genotype_allele_codes"] = geno_al
                logs.append({
                    "roi_path": roi_path,
                    "date_mount_id": date_mount_id,
                    "experiment_slug": slug,
                    "rule": rule_name,
                    "set_genotype_base_codes": geno_bc,
                    "set_genotype_allele_codes": geno_al,
                })
                filled += 1
                applied = True
                break

        if not applied:
            continue

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
        "rows_genotype_blank_before": int((df["genotype_base_codes"].astype(str).str.strip() == "").sum() + 0),
        "rows_filled_by_step4_defaults": int(filled),
    }]).to_csv(OUT_QC, sep="\t", index=False)

    pd.DataFrame(logs).to_csv(OUT_LOG, sep="\t", index=False)

    print(f"[OK] wrote {OUT_CSV} rows={len(df)} filled={filled}")
    print(f"[QC] wrote {OUT_QC}")
    print(f"[QC] wrote {OUT_LOG}")

if __name__ == "__main__":
    main()
