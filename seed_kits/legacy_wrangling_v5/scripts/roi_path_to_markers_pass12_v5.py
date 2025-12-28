from __future__ import annotations

from pathlib import Path
import re
import pandas as pd

ROOT = Path("~/Projects/carp_v2/seed_kits/legacy_wrangling_v5").expanduser()
RAW = ROOT / "raw"
WORKING = ROOT / "working"
QC = ROOT / "qc_runs"

IN_ROIS = WORKING / "roi_paths_from_foundation_v5.csv"
IN_XLSX = RAW / "2025-12-22-161955-Cell Observatory - Zebrafish Development.xlsx"
SHEET = "Master Imaging list"

IN_PLASMID_MAP = RAW / "Unique_injected_plasmid__preview_dqm.xlsx"
IN_RNA_MAP = RAW / "Unique_injected_rna__preview_dqm.xlsx"

OUT_CSV = WORKING / "roi_path_to_markers_pass12_v5.csv"
QC_MAIN = QC / "roi_path_to_markers_pass12_v5.qc.tsv"
QC_COVERAGE = QC / "roi_path_to_markers_pass12_v5.qc_coverage_by_experiment.tsv"
QC_UNMATCHED = QC / "roi_path_to_markers_pass12_v5.qc_unmatched_tokens_top.tsv"


RE_BASE = re.compile(r"(?i)\b([a-z]{2,8}-?\d{1,4})\b")
RE_ALLE = re.compile(r"(?i)\b(\d{2,4})\b")
RE_MGCO_NUM = re.compile(r"(?i)\bmgco[- ]?(\d{1,3})\b")
RE_PDQM_NUM = re.compile(r"(?i)\bpdqm[- ]?(\d{1,4})\b")

RE_SPLIT = re.compile(r"[;,|+]+|\s+|[()\[\]{}]+|:+|/+")


def _norm_pathish(s: str) -> str:
    s = str(s).strip().replace("\\", "/")
    return s


def parse_foundation_and_experiment_from_data_location(v: str) -> tuple[str | None, str | None]:
    """
    Deterministic: locate Aang_Foundation or Korra_Foundation in the string and take next segment as experiment_folder.
    Handles Windows paths like X:/abcabc/Korra_Foundation/20251217_mem-histone
    """
    s = _norm_pathish(v)
    for root in ("Aang_Foundation", "Korra_Foundation"):
        i = s.find(root + "/")
        if i >= 0:
            tail = s[i:]
            parts = [p for p in tail.split("/") if p]
            if len(parts) >= 2:
                return parts[0], parts[1]
    return None, None


def parse_foundation_and_experiment_from_roi_path(roi_path: str) -> tuple[str | None, str | None]:
    s = str(roi_path).strip().strip("/")
    parts = [p for p in s.split("/") if p]
    if len(parts) >= 2:
        return parts[0], parts[1]
    return None, None


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


def mgco_key_variants(tok: str) -> set[str]:
    """
    Deterministic canonicalization for MGCO tokens:
      - MGCO-04, MGCO04, MGCO4 -> MGCO-4 AND MGCO4 AND MGCO-04 etc
    We use this to increase match rate against the mapping table.
    """
    out: set[str] = set()
    t = str(tok).strip()
    if not t:
        return out
    m = RE_MGCO_NUM.search(t)
    if not m:
        return out
    n = int(m.group(1))
    out.add(f"MGCO-{n}")
    out.add(f"MGCO{n}")
    if n < 10:
        out.add(f"MGCO-0{n}")
        out.add(f"MGCO0{n}")
    return out


def normalize_mapping_keys(mapping: dict[str, str]) -> dict[str, str]:
    """
    Build an expanded lookup from observed variants to the same basecode.
    Only applies MGCO normalization deterministically.
    """
    out: dict[str, str] = {}
    for k, v in mapping.items():
        out[k] = v
        for kk in mgco_key_variants(k):
            out.setdefault(kk, v)
    return out


def extract_genotype_from_parent_string(s: str) -> tuple[list[str], list[str]]:
    """
    Deterministic minimal extraction:
      - basecode-like tokens: [a-z]{2,8}-?\d+
      - allele-like tokens: 2-4 digit numbers
    No pairing/inference; just emit sets.
    """
    if s is None:
        return [], []
    t = str(s)
    bases = sorted(set(m.group(1).lower() for m in RE_BASE.finditer(t)))
    alles = sorted(set(m.group(1) for m in RE_ALLE.finditer(t)))
    return bases, alles


def main() -> None:
    for p in (IN_ROIS, IN_XLSX, IN_PLASMID_MAP, IN_RNA_MAP):
        if not p.exists():
            raise SystemExit(f"[STOP] missing input: {p}")

    WORKING.mkdir(parents=True, exist_ok=True)
    QC.mkdir(parents=True, exist_ok=True)

    rois = pd.read_csv(IN_ROIS)
    if "roi_path" not in rois.columns:
        raise SystemExit("[STOP] roi_paths_from_foundation_v5.csv missing roi_path")

    rois = rois.copy()
    rois["foundation_root"], rois["experiment_folder"] = zip(*rois["roi_path"].map(parse_foundation_and_experiment_from_roi_path))

    x = pd.read_excel(IN_XLSX, sheet_name=SHEET)

    need_cols = {
        "Data location",
        "ZF female genotype",
        "ZF male genotype",
        "additional plasmids injected",
        "additional mRNAs injected",
        "additonal dye and chemicals",
    }
    missing = sorted(c for c in need_cols if c not in x.columns)
    if missing:
        raise SystemExit(f"[STOP] {IN_XLSX.name}:{SHEET} missing columns: {missing}")

    x = x.copy()
    x["foundation_root"], x["experiment_folder"] = zip(*x["Data location"].map(parse_foundation_and_experiment_from_data_location))
    x_good = x[x["foundation_root"].notna() & x["experiment_folder"].notna()].copy()

    # collapse to one row per (foundation_root, experiment_folder)
    # deterministic: if multiple rows exist, keep them all for QC and mark ambiguous; do not guess.
    grp = x_good.groupby(["foundation_root", "experiment_folder"], dropna=False)
    exp_rows = grp.size().rename("n_excel_rows").reset_index()

    # choose a representative row only when unique
    unique_keys = exp_rows[exp_rows["n_excel_rows"] == 1][["foundation_root", "experiment_folder"]]
    unique_set = set(map(tuple, unique_keys.values.tolist()))

    rep = []
    ambiguous = 0
    for (fr, ef), sub in grp:
        if (fr, ef) in unique_set:
            r = sub.iloc[0]
            rep.append(r)
        else:
            ambiguous += 1
    rep = pd.DataFrame(rep)

    # join ROIs to unique experiment metadata only
    meta = rep[
        [
            "foundation_root",
            "experiment_folder",
            "ZF female genotype",
            "ZF male genotype",
            "additional plasmids injected",
            "additional mRNAs injected",
            "additonal dye and chemicals",
        ]
    ].copy()

    out = rois.merge(meta, on=["foundation_root", "experiment_folder"], how="left")

    # map injections to basecodes
    map_pl = normalize_mapping_keys(load_map_plasmid())
    map_rna = normalize_mapping_keys(load_map_rna())

    unmatched_counter: dict[str, int] = {}

    def inj_to_codes(v: str, mapping: dict[str, str]) -> list[str]:
        toks = split_tokens(v)
        codes: set[str] = set()
        for tok in toks:
            hit = False
            if tok in mapping:
                codes.add(mapping[tok])
                hit = True
            else:
                for kk in mgco_key_variants(tok):
                    if kk in mapping:
                        codes.add(mapping[kk])
                        hit = True
                        break
            if not hit and tok:
                unmatched_counter[tok] = unmatched_counter.get(tok, 0) + 1
        return sorted(codes)

    # genotype extraction (no inference)
    geno_bases = []
    geno_alles = []
    for _, r in out.iterrows():
        b1, a1 = extract_genotype_from_parent_string(r.get("ZF female genotype"))
        b2, a2 = extract_genotype_from_parent_string(r.get("ZF male genotype"))
        geno_bases.append(";".join(sorted(set(b1) | set(b2))))
        geno_alles.append(";".join(sorted(set(a1) | set(a2))))
    out["genotype_base_codes"] = geno_bases
    out["genotype_allele_codes"] = geno_alles

    out["treatment_plasmid_base_codes"] = out["additional plasmids injected"].apply(lambda v: ";".join(inj_to_codes(v, map_pl)) if pd.notna(v) else "")
    out["treatment_rna_base_codes"] = out["additional mRNAs injected"].apply(lambda v: ";".join(inj_to_codes(v, map_rna)) if pd.notna(v) else "")

    # dyes: no basecode mapping available in v5/raw; preserve empty but keep raw for QC later if needed
    out["treatment_dye_text"] = out["additonal dye and chemicals"].fillna("").astype(str)

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

    # QC
    rois_total = len(rois)
    rois_with_unique_exp = out["ZF female genotype"].notna().sum()
    pd.DataFrame([{
        "roi_paths_total": int(rois_total),
        "excel_rows_total": int(len(x)),
        "excel_rows_with_foundation_path": int(len(x_good)),
        "unique_experiment_keys": int(len(unique_set)),
        "ambiguous_experiment_keys": int(ambiguous),
        "roi_paths_with_unique_experiment_link": int(rois_with_unique_exp),
        "roi_paths_missing_experiment_link": int(rois_total - rois_with_unique_exp),
        "unmatched_injection_token_unique": int(len(unmatched_counter)),
    }]).to_csv(QC_MAIN, sep="\t", index=False)

    cov = out.groupby(["foundation_root", "experiment_folder"], dropna=False).agg(
        roi_count=("roi_path", "size"),
        has_meta=("ZF female genotype", lambda s: int(s.notna().any())),
    ).reset_index()
    cov.to_csv(QC_COVERAGE, sep="\t", index=False)

    top_unmatched = (
        pd.DataFrame([{"token": k, "roi_count": v} for k, v in unmatched_counter.items()])
        .sort_values(["roi_count", "token"], ascending=[False, True])
        .head(200)
    )
    top_unmatched.to_csv(QC_UNMATCHED, sep="\t", index=False)

    print(f"[OK] wrote {OUT_CSV} rows={len(final)}")
    print(f"[QC] wrote {QC_MAIN}")
    print(f"[QC] wrote {QC_COVERAGE}")
    print(f"[QC] wrote {QC_UNMATCHED}")


if __name__ == "__main__":
    main()
