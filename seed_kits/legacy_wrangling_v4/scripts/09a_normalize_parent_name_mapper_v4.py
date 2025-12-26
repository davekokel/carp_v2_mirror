from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

IN_XLSX = Path("seed_kits/legacy_wrangling_v2/raw/Unique_parent_names__mom_dad_combined__preview_dqm.xlsx")
SHEET = "Sheet 1 - Unique_parent_names__"

OUT_TSV = Path("seed_kits/legacy_wrangling_v4/working/parent_name_mapper_v4.tsv")
OUT_QC_DUP = Path("seed_kits/legacy_wrangling_v4/qc/parent_name_mapper_v4__dupes.tsv")
OUT_QC_MISS = Path("seed_kits/legacy_wrangling_v4/qc/parent_name_mapper_v4__missing.tsv")

def s(x: object) -> str:
    if x is None:
        return ""
    t = str(x).strip()
    if t.lower() in ("nan", "none", "na", "n/a", "<na>"):
        return ""
    return t

def norm_base_codes(blob: object) -> str:
    t = s(blob)
    if not t:
        return ""
    parts = [p.strip() for p in re.split(r"[|,;]+", t) if p.strip()]
    out = []
    seen = set()
    for p in parts:
        p = p.replace("pDQM", "pdqm").replace("PDQM", "pdqm")
        p = p.replace("pSWIN", "pswin").replace("PSWIN", "pswin")
        p = p.replace("MGCO", "mgco")
        p = p.lower()
        p = re.sub(r"[^a-z0-9\-]+", "", p)
        m = re.match(r"^([a-z]+)-?0*([0-9]+)$", p)
        if m:
            p = f"{m.group(1)}-{int(m.group(2))}"
        if p and p not in seen:
            seen.add(p)
            out.append(p)
    return "|".join(out)

def norm_alleles(blob: object) -> str:
    t = s(blob)
    if not t:
        return ""
    parts = [p.strip() for p in re.split(r"[|,;]+", t) if p.strip()]
    out = []
    for p in parts:
        try:
            f = float(p)
            out.append(str(int(f)) if f.is_integer() else str(p).strip())
        except Exception:
            out.append(str(p).strip())
    return "|".join(out)

def norm_parent_name(name: object) -> str:
    t = s(name)
    t = re.sub(r"\s+", " ", t).strip()
    return t

def main() -> None:
    if not IN_XLSX.exists():
        raise SystemExit(f"[STOP] missing XLSX: {IN_XLSX}")

    df = pd.read_excel(IN_XLSX, sheet_name=SHEET, dtype=str, keep_default_na=False, na_filter=False).fillna("")
    df.columns = [str(c).strip() for c in df.columns]

    need = ["parent_fish_name", "plasmid_base_code", "allele", "injected_rna", "injected_plasmid"]
    miss = [c for c in need if c not in df.columns]
    if miss:
        raise SystemExit(f"[STOP] mapper XLSX missing columns: {miss}")

    out = pd.DataFrame({
        "parent_fish_name_raw": df["parent_fish_name"].map(s),
        "parent_fish_name_norm": df["parent_fish_name"].map(norm_parent_name),
        "genotype_base_codes": df["plasmid_base_code"].map(norm_base_codes),
        "genotype_allele_codes": df["allele"].map(norm_alleles),
        "injected_rna_base_codes": df["injected_rna"].map(norm_base_codes),
        "injected_plasmid_base_codes": df["injected_plasmid"].map(norm_base_codes),
    })

    out = out[out["parent_fish_name_norm"].ne("")].copy()

    dup = (
        out.groupby("parent_fish_name_norm", as_index=False)
        .agg(
            n=("parent_fish_name_norm", "size"),
            genotype_base_codes=("genotype_base_codes", lambda x: ";".join(sorted({s(v) for v in x if s(v)}))),
            genotype_allele_codes=("genotype_allele_codes", lambda x: ";".join(sorted({s(v) for v in x if s(v)}))),
            injected_rna_base_codes=("injected_rna_base_codes", lambda x: ";".join(sorted({s(v) for v in x if s(v)}))),
            injected_plasmid_base_codes=("injected_plasmid_base_codes", lambda x: ";".join(sorted({s(v) for v in x if s(v)}))),
        )
    )
    dup_bad = dup[dup["n"].astype(int) > 1].copy()

    missing = out[
        (out["genotype_base_codes"].eq("") & out["genotype_allele_codes"].eq(""))
        & (out["injected_rna_base_codes"].eq("") & out["injected_plasmid_base_codes"].eq(""))
    ][["parent_fish_name_raw", "parent_fish_name_norm"]].drop_duplicates().copy()

    OUT_TSV.parent.mkdir(parents=True, exist_ok=True)
    OUT_QC_DUP.parent.mkdir(parents=True, exist_ok=True)

    out = out.drop_duplicates(subset=["parent_fish_name_norm"], keep="first").copy()
    out.to_csv(OUT_TSV, sep="\t", index=False)

    dup_bad.to_csv(OUT_QC_DUP, sep="\t", index=False)
    missing.to_csv(OUT_QC_MISS, sep="\t", index=False)

    print(OUT_TSV)
    print("[QC] rows", len(out))
    print("[QC] dup_parent_names", len(dup_bad), str(OUT_QC_DUP))
    print("[QC] missing_all_signals", len(missing), str(OUT_QC_MISS))

if __name__ == "__main__":
    main()
