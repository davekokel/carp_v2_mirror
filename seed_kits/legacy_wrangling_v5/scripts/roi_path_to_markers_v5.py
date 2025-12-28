from __future__ import annotations

from pathlib import Path
import re
import pandas as pd

ROOT = Path("~/Projects/carp_v2/seed_kits/legacy_wrangling_v5").expanduser()
RAW = ROOT / "raw"
WORKING = ROOT / "working"
QC = ROOT / "qc_runs"

IN_ROIS = WORKING / "roi_paths_from_foundation_v5.csv"
IN_PER_ROI = RAW / "roi_missing_parents_for_manual_mapping_DQM_CNH (1).csv"
IN_PLASMID_MAP = RAW / "Unique_injected_plasmid__preview_dqm.xlsx"
IN_RNA_MAP = RAW / "Unique_injected_rna__preview_dqm.xlsx"

OUT_CSV = WORKING / "roi_path_to_markers_v5.csv"
QC_MAIN = QC / "roi_path_to_markers_v5.qc.tsv"
QC_FILL = QC / "roi_path_to_markers_v5.qc_fill_rates.tsv"
QC_MISSING = QC / "roi_path_to_markers_v5.qc_missing_samples.tsv"
QC_UNMATCHED = QC / "roi_path_to_markers_v5.qc_unmatched_tokens_top.tsv"

RE_SPLIT = re.compile(r"[;,|+]+|\s+|[()\[\]{}]+|:+|/+")

def norm_foundation_root(s: str) -> str:
    s = str(s).strip().lstrip("./")
    for root in ("Aang_Foundation/", "Korra_Foundation/"):
        i = s.find(root)
        if i >= 0:
            return s[i:]
    return s

def split_tokens(s: str) -> list[str]:
    if s is None:
        return []
    t = str(s).strip()
    if not t or t.lower() in ("nan", "none"):
        return []
    t = t.replace(",", " ")
    toks = [x.strip().strip(".") for x in RE_SPLIT.split(t) if x and x.strip()]
    return [x for x in toks if x]

def load_map_plasmid() -> dict[str, str]:
    x = pd.read_excel(IN_PLASMID_MAP)
    need = {"injected_plasmid", "plasmid_base_code"}
    if not need.issubset(set(x.columns)):
        raise SystemExit(f"[STOP] {IN_PLASMID_MAP.name} missing columns: {sorted(need - set(x.columns))}")
    m: dict[str, str] = {}
    for a, b in zip(x["injected_plasmid"], x["plasmid_base_code"]):
        if pd.isna(a) or pd.isna(b):
            continue
        k = str(a).strip()
        v = str(b).strip()
        if k and v:
            m[k] = v
    return m

def load_map_rna() -> dict[str, str]:
    x = pd.read_excel(IN_RNA_MAP)
    need = {"injected_rna", "plasmid_base_code"}
    if not need.issubset(set(x.columns)):
        raise SystemExit(f"[STOP] {IN_RNA_MAP.name} missing columns: {sorted(need - set(x.columns))}")
    m: dict[str, str] = {}
    for a, b in zip(x["injected_rna"], x["plasmid_base_code"]):
        if pd.isna(a) or pd.isna(b):
            continue
        k = str(a).strip()
        v = str(b).strip()
        if k and v:
            m[k] = v
    return m

def main() -> None:
    for p in (IN_ROIS, IN_PER_ROI, IN_PLASMID_MAP, IN_RNA_MAP):
        if not p.exists():
            raise SystemExit(f"[STOP] missing input: {p}")

    WORKING.mkdir(parents=True, exist_ok=True)
    QC.mkdir(parents=True, exist_ok=True)

    rois = pd.read_csv(IN_ROIS)
    if "roi_path" not in rois.columns:
        raise SystemExit("[STOP] roi_paths_from_foundation_v5.csv missing roi_path")

    per = pd.read_csv(IN_PER_ROI)
    need_per = {"roi_dir", "injection plasmid"}
    if not need_per.issubset(set(per.columns)):
        raise SystemExit(f"[STOP] {IN_PER_ROI.name} missing columns: {sorted(need_per - set(per.columns))}")

    rois = rois.copy()
    rois["roi_path"] = rois["roi_path"].map(norm_foundation_root)

    per = per.copy()
    per["roi_path"] = per["roi_dir"].map(norm_foundation_root)
    per["inj_text"] = per["injection plasmid"].astype(str)

    map_pl = load_map_plasmid()
    map_rna = load_map_rna()

    rows = []
    unmatched_counter: dict[str, int] = {}

    g = per.groupby("roi_path", dropna=False)
    for roi_path, sub in g:
        toks: list[str] = []
        for v in sub["inj_text"].tolist():
            toks.extend(split_tokens(v))

        pl_codes: set[str] = set()
        rna_codes: set[str] = set()
        unmatched: set[str] = set()

        for tok in toks:
            hit = False
            if tok in map_pl:
                pl_codes.add(map_pl[tok])
                hit = True
            if tok in map_rna:
                rna_codes.add(map_rna[tok])
                hit = True
            if not hit:
                unmatched.add(tok)

        for tok in unmatched:
            unmatched_counter[tok] = unmatched_counter.get(tok, 0) + 1

        rows.append(
            {
                "roi_path": str(roi_path),
                "treatment_plasmid_base_codes": ";".join(sorted(pl_codes)),
                "treatment_rna_base_codes": ";".join(sorted(rna_codes)),
                "_source_rows": int(len(sub)),
                "_unmatched_tokens": ";".join(sorted(unmatched)),
            }
        )

    agg = pd.DataFrame(rows)

    out = rois.merge(agg, on="roi_path", how="left")

    out["genotype_base_codes"] = ""
    out["genotype_allele_codes"] = ""

    out["treatment_plasmid_base_codes"] = out["treatment_plasmid_base_codes"].fillna("")
    out["treatment_rna_base_codes"] = out["treatment_rna_base_codes"].fillna("")

    final = out[
        [
            "roi_path",
            "genotype_base_codes",
            "genotype_allele_codes",
            "treatment_rna_base_codes",
            "treatment_plasmid_base_codes",
        ]
    ].copy()

    final.to_csv(OUT_CSV, index=False)

    have_per = out["_source_rows"].notna().sum()
    fill = {
        "genotype_base_codes": float((final["genotype_base_codes"].astype(str).str.len() > 0).mean()),
        "genotype_allele_codes": float((final["genotype_allele_codes"].astype(str).str.len() > 0).mean()),
        "treatment_rna_base_codes": float((final["treatment_rna_base_codes"].astype(str).str.len() > 0).mean()),
        "treatment_plasmid_base_codes": float((final["treatment_plasmid_base_codes"].astype(str).str.len() > 0).mean()),
    }

    pd.DataFrame([{
        "roi_paths_total": int(len(final)),
        "roi_paths_with_per_roi_rows": int(have_per),
        "roi_paths_missing_per_roi_rows": int(len(final) - have_per),
        "agg_unique_roi_paths": int(agg["roi_path"].nunique()) if len(agg) else 0,
        "unmatched_token_unique": int(len(unmatched_counter)),
    }]).to_csv(QC_MAIN, sep="\t", index=False)

    pd.DataFrame([{"field": k, "fill_rate": v} for k, v in fill.items()]).to_csv(QC_FILL, sep="\t", index=False)

    diag = out.copy()
    diag["has_any_treatment"] = (
        (diag["treatment_rna_base_codes"].astype(str).str.len() > 0)
        | (diag["treatment_plasmid_base_codes"].astype(str).str.len() > 0)
    )
    missing = diag.loc[~diag["has_any_treatment"], ["roi_path", "_source_rows", "_unmatched_tokens"]].head(500)
    missing.to_csv(QC_MISSING, sep="\t", index=False)

    top_unmatched = (
        pd.DataFrame([{"token": k, "roi_path_count": v} for k, v in unmatched_counter.items()])
        .sort_values(["roi_path_count", "token"], ascending=[False, True])
        .head(200)
    )
    top_unmatched.to_csv(QC_UNMATCHED, sep="\t", index=False)

    print(f"[OK] wrote {OUT_CSV} rows={len(final)}")
    print(f"[QC] wrote {QC_MAIN}")
    print(f"[QC] wrote {QC_FILL}")
    print(f"[QC] wrote {QC_MISSING}")
    print(f"[QC] wrote {QC_UNMATCHED}")

if __name__ == "__main__":
    main()
