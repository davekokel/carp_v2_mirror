from __future__ import annotations

import argparse
import hashlib
import re
from pathlib import Path

import pandas as pd

EMPTY_SIG = "plasmids=|rnas=|dyes="

def _s(x: object) -> str:
    if x is None:
        return ""
    s = str(x).strip()
    if s.lower() in ("nan", "none", "na", "n/a", "<na>"):
        return ""
    return s

def _norm_pipe_blob(blob: object) -> str:
    s = _s(blob).lower()
    if not s:
        return ""
    toks = [t.strip() for t in re.split(r"[|,;]+", s) if t.strip()]
    out = []
    seen = set()
    for t in toks:
        t = re.sub(r"[^a-z0-9\-]+", "", t)
        m = re.match(r"^([a-z]+)-?0*([0-9]+)$", t)
        if m:
            t = f"{m.group(1)}-{int(m.group(2))}"
        if t and t not in seen:
            seen.add(t)
            out.append(t)
    return "|".join(out)

def _norm_alleles_pipe(blob: object) -> str:
    s = _s(blob)
    if not s:
        return ""
    parts = [p.strip() for p in s.replace(",", "|").replace(";", "|").split("|") if p.strip()]
    out = []
    for p in parts:
        try:
            f = float(p)
            out.append(str(int(f)) if f.is_integer() else str(p).strip())
        except Exception:
            out.append(str(p).strip())
    return "|".join(out)

def _treat_code_from_signature(sig: str) -> str:
    s = _s(sig)
    if not s or s == EMPTY_SIG:
        return ""
    h = hashlib.sha1(s.encode("utf-8")).hexdigest()[:10]
    return f"T-EXP-{h}"

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--roi-tsv", default="seed_kits/legacy_wrangling_v4/working/ideal_roi_universe_v4.tsv")
    ap.add_argument("--geno-tsv", default="seed_kits/legacy_wrangling_v4/working/ideal_with_genotypes_v4.tsv")
    ap.add_argument("--treat-tsv", default="seed_kits/legacy_wrangling_v4/working/ideal_with_treatments_v4.tsv")
    ap.add_argument("--out", default="seed_kits/legacy_wrangling_v4/working/ideal_imaging_import_sheet_v4.fixed.tsv")
    args = ap.parse_args()

    roi_tsv = Path(args.roi_tsv)
    geno_tsv = Path(args.geno_tsv)
    treat_tsv = Path(args.treat_tsv)
    out = Path(args.out)

    for p in [roi_tsv, geno_tsv, treat_tsv]:
        if not p.exists():
            raise SystemExit(f"[STOP] missing input: {p}")

    roi = pd.read_csv(roi_tsv, sep="\t", dtype=str, keep_default_na=False, na_filter=False)
    roi.columns = [str(c).strip() for c in roi.columns]
    if "roi_path" not in roi.columns:
        raise SystemExit("[STOP] roi-tsv missing roi_path")
    roi["roi_path"] = roi["roi_path"].map(_s)

    g = pd.read_csv(geno_tsv, sep="\t", dtype=str, keep_default_na=False, na_filter=False)
    g.columns = [str(c).strip() for c in g.columns]
    if "roi_path" not in g.columns:
        raise SystemExit("[STOP] geno-tsv missing roi_path")
    g["roi_path"] = g["roi_path"].map(_s)

    t = pd.read_csv(treat_tsv, sep="\t", dtype=str, keep_default_na=False, na_filter=False)
    t.columns = [str(c).strip() for c in t.columns]
    if "roi_path" not in t.columns:
        raise SystemExit("[STOP] treat-tsv missing roi_path")
    t["roi_path"] = t["roi_path"].map(_s)

    roi_set = set(roi["roi_path"].tolist())
    g_set = set(g["roi_path"].tolist())
    t_set = set(t["roi_path"].tolist())

    if roi_set != g_set:
        extra = sorted(list(g_set - roi_set))[:10]
        missing = sorted(list(roi_set - g_set))[:10]
        raise SystemExit(f"[STOP] geno roi_path set mismatch. extra_in_geno={len(g_set-roi_set)} missing_in_geno={len(roi_set-g_set)} sample_extra={extra} sample_missing={missing}")
    if roi_set != t_set:
        extra = sorted(list(t_set - roi_set))[:10]
        missing = sorted(list(roi_set - t_set))[:10]
        raise SystemExit(f"[STOP] treat roi_path set mismatch. extra_in_treat={len(t_set-roi_set)} missing_in_treat={len(roi_set-t_set)} sample_extra={extra} sample_missing={missing}")

    df = roi.merge(g, on="roi_path", how="left").merge(t, on="roi_path", how="left")

    df["genotype_base_codes"] = df.get("genotype_base_codes", "").map(_norm_pipe_blob)
    df["genotype_allele_codes"] = df.get("genotype_allele_codes", "").map(_norm_alleles_pipe)
    df["treatment_plasmid_base_codes"] = df.get("treatment_plasmid_base_codes", "").map(_norm_pipe_blob)
    df["treatment_rna_base_codes"] = df.get("treatment_rna_base_codes", "").map(_norm_pipe_blob)

    df["signature_text"] = df.get("signature_text", "").map(_s)
    df.loc[df["signature_text"].eq(""), "signature_text"] = df.apply(
        lambda r: f"plasmids={','.join(sorted([x for x in _s(r.get('treatment_plasmid_base_codes')).split('|') if x]))}|rnas={','.join(sorted([x for x in _s(r.get('treatment_rna_base_codes')).split('|') if x]))}|dyes=",
        axis=1,
    )
    df["signature_text"] = df["signature_text"].map(_s)
    df.loc[df["signature_text"].eq("plasmids=|rnas=|dyes="), "signature_text"] = EMPTY_SIG

    df["treat_code"] = df.get("treat_code", "").map(_s)
    df.loc[df["treat_code"].eq(""), "treat_code"] = df["signature_text"].map(_treat_code_from_signature)

    if "include_in_db" not in df.columns:
        df["include_in_db"] = "true"
    df["include_in_db"] = df["include_in_db"].map(_s)
    if "dataset_slug" in df.columns:
        df.loc[df["dataset_slug"].map(_s).str.lower().eq("analysis_test"), "include_in_db"] = "false"

    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, sep="\t", index=False)
    print(str(out))
    print("[QC] rows", len(df))

if __name__ == "__main__":
    main()
