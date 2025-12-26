from __future__ import annotations

import argparse
import re
from pathlib import Path
import pandas as pd

IN_ROI = Path("seed_kits/legacy_wrangling_v2/raw/roi_missing_parents_for_manual_mapping_DQM_CNH (1).csv")
IN_PARENT = Path("seed_kits/legacy_wrangling_v4/working/parent_name_mapper_v4.tsv")

OUT_TSV = Path("seed_kits/legacy_wrangling_v4/working/roi_parent_injection_resolver_v4.tsv")
QC_UNMAPPED = Path("seed_kits/legacy_wrangling_v4/qc/roi_parent_injection_resolver_v4__unmapped_parents.tsv")
QC_UNPARSED_INJ = Path("seed_kits/legacy_wrangling_v4/qc/roi_parent_injection_resolver_v4__unparsed_injection.tsv")

def s(x: object) -> str:
    if x is None:
        return ""
    t = str(x).strip()
    if t.lower() in ("nan","none","na","n/a","<na>"):
        return ""
    return t

def norm_codes_pipe(x: object) -> str:
    t = s(x)
    if not t or t.lower() in ("n/a","na"):
        return ""
    parts = [p.strip() for p in re.split(r"[|,;]+", t) if p.strip()]
    out = []
    seen = set()
    for p in parts:
        p = p.replace("pDQM","pdqm").replace("PDQM","pdqm").replace("pSWIN","pswin").replace("PSWIN","pswin").replace("MGCO","mgco")
        p = p.lower()
        p = re.sub(r"[^a-z0-9\-]+", "", p)
        m = re.match(r"^([a-z]+)-?0*([0-9]+)$", p)
        if m:
            p = f"{m.group(1)}-{int(m.group(2))}"
        if p and p not in seen:
            seen.add(p)
            out.append(p)
    return "|".join(out)

def split_codes_csv(x: object) -> list[str]:
    t = norm_codes_pipe(x)
    if not t:
        return []
    return [p for p in t.split("|") if p]

def norm_injection_type(x: object) -> str:
    t = s(x).lower()
    t = t.replace(" ", "").replace("-", "").replace("_", "")
    if t in ("mrna","rna"):
        return "rna"
    if t in ("plasmid","dna"):
        return "plasmid"
    if t == "":
        return ""
    return t

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in-roi", default=str(IN_ROI))
    ap.add_argument("--in-parent", default=str(IN_PARENT))
    ap.add_argument("--out", default=str(OUT_TSV))
    args = ap.parse_args()

    in_roi = Path(args.in_roi)
    in_parent = Path(args.in_parent)
    out = Path(args.out)

    if not in_roi.exists():
        raise SystemExit(f"[STOP] missing roi csv: {in_roi}")
    if not in_parent.exists():
        raise SystemExit(f"[STOP] missing parent mapper: {in_parent}")

    roi = pd.read_csv(in_roi, dtype=str, keep_default_na=False, na_filter=False).fillna("")
    roi.columns = [str(c).strip() for c in roi.columns]

    need_roi = ["roi_dir", "mother_fish_manual", "father_fish_manual", "injection type", "injection plasmid"]
    miss = [c for c in need_roi if c not in roi.columns]
    if miss:
        raise SystemExit(f"[STOP] roi csv missing columns: {miss}")

    roi = roi.copy()
    roi["roi_path"] = roi["roi_dir"].map(s)
    roi = roi[roi["roi_path"].ne("")].copy()

    roi["mother_name_raw"] = roi["mother_fish_manual"].map(s)
    roi["father_name_raw"] = roi["father_fish_manual"].map(s)
    roi["inj_type_norm"] = roi["injection type"].map(norm_injection_type)
    roi["inj_type_raw"] = roi["injection type"].map(s)
    roi["inj_blob"] = roi["injection plasmid"].map(s)

    parent = pd.read_csv(in_parent, sep="\t", dtype=str, keep_default_na=False, na_filter=False).fillna("")
    parent.columns = [str(c).strip() for c in parent.columns]

    need_parent = ["parent_fish_name_norm", "genotype_base_codes", "genotype_allele_codes", "injected_rna_base_codes", "injected_plasmid_base_codes"]
    miss2 = [c for c in need_parent if c not in parent.columns]
    if miss2:
        raise SystemExit(f"[STOP] parent mapper missing columns: {miss2}")

    parent = parent.copy()
    parent["parent_fish_name_norm"] = parent["parent_fish_name_norm"].map(s)
    parent = parent[parent["parent_fish_name_norm"].ne("")].copy()

    pmap = parent.set_index("parent_fish_name_norm", drop=False)

    def lookup_parent(name: str) -> dict:
        n = s(name)
        if not n:
            return {"geno_bc":"", "geno_al":"", "inj_rna":"", "inj_plas":""}
        if n not in pmap.index:
            return {"geno_bc":"", "geno_al":"", "inj_rna":"", "inj_plas":""}
        r = pmap.loc[n]
        if isinstance(r, pd.DataFrame):
            r = r.iloc[0]
        return {
            "geno_bc": s(r.get("genotype_base_codes","")),
            "geno_al": s(r.get("genotype_allele_codes","")),
            "inj_rna": s(r.get("injected_rna_base_codes","")),
            "inj_plas": s(r.get("injected_plasmid_base_codes","")),
        }

    out_rows = []
    unmapped_parent_rows = []

    unparsed_inj_rows = []

    for r in roi.itertuples(index=False):
        roi_path = s(getattr(r, "roi_path"))
        mom = s(getattr(r, "mother_name_raw"))
        dad = s(getattr(r, "father_name_raw"))

        mom_lu = lookup_parent(mom)
        dad_lu = lookup_parent(dad)

        if (mom and mom not in pmap.index) or (dad and dad not in pmap.index):
            unmapped_parent_rows.append({
                "roi_path": roi_path,
                "mother_fish_manual": mom,
                "father_fish_manual": dad,
            })

        geno_bc_parts = []
        geno_al_parts = []

        for lu in (mom_lu, dad_lu):
            bc = norm_codes_pipe(lu["geno_bc"])
            al = s(lu["geno_al"])
            if bc and al:
                geno_bc_parts.append(bc)
                geno_al_parts.append(al)

        genotype_base_codes = "|".join([p for p in geno_bc_parts if p])
        genotype_allele_codes = "|".join([p for p in geno_al_parts if p])

        inj_type = s(getattr(r, "inj_type_norm"))
        inj_blob = s(getattr(r, "inj_blob"))

        inj_codes = split_codes_csv(inj_blob)

        treatment_rna_base_codes = ""
        treatment_plasmid_base_codes = ""

        if inj_codes and inj_type in ("rna","plasmid"):
            if inj_type == "rna":
                treatment_rna_base_codes = "|".join(inj_codes)
            else:
                treatment_plasmid_base_codes = "|".join(inj_codes)
        elif inj_codes and inj_type not in ("rna","plasmid"):
            unparsed_inj_rows.append({
                "roi_path": roi_path,
                "injection_type_raw": s(getattr(r, "inj_type_raw")),
                "injection_type_norm": inj_type,
                "injection_plasmid_raw": inj_blob,
            })

        out_rows.append({
            "roi_path": roi_path,
            "mother_fish_manual": mom,
            "father_fish_manual": dad,
            "genotype_base_codes": genotype_base_codes,
            "genotype_allele_codes": genotype_allele_codes,
            "treatment_plasmid_base_codes": treatment_plasmid_base_codes,
            "treatment_rna_base_codes": treatment_rna_base_codes,
            "source_of_genotype": "parent_name_mapper_v4",
            "source_of_treatment": "roi_missing_parents_manual",
        })

    out_df = pd.DataFrame(out_rows)
    out.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(out, sep="\t", index=False)

    QC_UNMAPPED.parent.mkdir(parents=True, exist_ok=True)
    QC_UNPARSED_INJ.parent.mkdir(parents=True, exist_ok=True)

    pd.DataFrame(unmapped_parent_rows).drop_duplicates().to_csv(QC_UNMAPPED, sep="\t", index=False)
    pd.DataFrame(unparsed_inj_rows).drop_duplicates().to_csv(QC_UNPARSED_INJ, sep="\t", index=False)

    print(str(out))
    print("[QC] rows", len(out_df))
    print("[QC] unmapped_parents", len(pd.DataFrame(unmapped_parent_rows).drop_duplicates()), str(QC_UNMAPPED))
    print("[QC] unparsed_injection", len(pd.DataFrame(unparsed_inj_rows).drop_duplicates()), str(QC_UNPARSED_INJ))

if __name__ == "__main__":
    main()
