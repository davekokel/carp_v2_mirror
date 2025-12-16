from __future__ import annotations

import os
import re
import hashlib
from pathlib import Path
import pandas as pd
from sqlalchemy import create_engine, text

ROOT = Path("/Users/davekokel/Projects/carp_v2")
V3 = ROOT / "seed_kits" / "legacy_wrangling_v3"
WORK = V3 / "working"
QC = V3 / "qc"
QC.mkdir(parents=True, exist_ok=True)

ANN = WORK / "legacy_imaging_annotations_for_db_v9.csv"
OUT = WORK / "v3_roi_biology_map_v1.csv"

def norm_str(x) -> str:
    if pd.isna(x):
        return ""
    s = str(x).strip()
    return "" if s.lower() in ("nan", "<na>", "none") else s

def norm_basecode_token(tok: str) -> str:
    t = tok.strip()
    if not t:
        return ""
    t = re.sub(r"\(.*?\)", "", t).strip()
    m = re.match(r"^(pdqm|pDQM)\s*0*([0-9]+)$", t)
    if m:
        return f"pdqm-{int(m.group(2))}"
    m = re.match(r"^(mgco|MGCO)\s*0*([0-9]+)$", t)
    if m:
        return f"mgco-{int(m.group(2))}"
    m = re.match(r"^(pdqm|pDQM)\s*-\s*0*([0-9]+)$", t)
    if m:
        return f"pdqm-{int(m.group(2))}"
    m = re.match(r"^(mgco|MGCO)\s*-\s*0*([0-9]+)$", t)
    if m:
        return f"mgco-{int(m.group(2))}"
    return t.lower()

def split_codes(s: str) -> list[str]:
    if not s:
        return []
    parts = re.split(r"[|,;]+", s)
    out = []
    for p in parts:
        p = p.strip()
        if p:
            out.append(p)
    return out

def parse_pdqm_codes(raw: str) -> list[str]:
    out = []
    for tok in split_codes(raw):
        bc = norm_basecode_token(tok)
        if bc.startswith("pdqm-"):
            out.append(bc)
    return sorted(set(out))

def parse_mgco_codes(raw: str) -> list[str]:
    out = []
    for tok in split_codes(raw):
        bc = norm_basecode_token(tok)
        if bc.startswith("mgco-"):
            out.append(bc)
    return sorted(set(out))

def parse_allele_nicknames(raw: str) -> list[str]:
    out = []
    for tok in split_codes(raw):
        tok = tok.strip()
        if not tok:
            continue
        try:
            out.append(str(int(float(tok))))
        except Exception:
            out.append(tok)
    return sorted(set(out))

def make_geno_cache_string_fk(resolved_pairs: list[tuple[str,int]]) -> str:
    parts = [f"{b}:{n}" for b,n in resolved_pairs]
    return ",".join(parts)

def gcode(geno_str: str) -> str:
    h = hashlib.sha256(geno_str.encode("utf-8")).hexdigest()[:8]
    return f"G-{h}"

def main() -> None:
    db_url = os.environ.get("DB_URL")
    if not db_url:
        raise SystemExit("DB_URL not set")

    eng = create_engine(db_url)
    df = pd.read_csv(ANN)

    need = ["bruker_roi_id", "experiment_folder", "dataset_slug", "roi_dir"]
    for c in need:
        if c not in df.columns:
            df[c] = pd.NA

    df["bruker_roi_id"] = df["bruker_roi_id"].astype("string")

    with eng.begin() as cx:
        rows = cx.execute(text("""
          SELECT roi_code AS bruker_roi_id, clutch_code, treated_clutch_code, treatment_code, genotype_code
          FROM public.v_roi_overview_all
        """)).fetchall()
    m = pd.DataFrame(rows, columns=["bruker_roi_id","db_clutch_code","db_treated_clutch_code","db_treatment_code","db_genotype_code"])
    m["bruker_roi_id"] = m["bruker_roi_id"].astype("string")

    df = df.merge(m, on="bruker_roi_id", how="left")

    df["v2_genotype_base_codes"] = df.get("genotype_base_codes", pd.Series([""]*len(df))).apply(norm_str)
    df["v2_genotype_allele_codes"] = df.get("genotype_allele_codes", pd.Series([""]*len(df))).apply(norm_str)

    inj_cols = [
        "additional plasmids injected",
        "additional mRNAs injected",
        "treatment_plasmid_names_sheet",
        "treatment_rna_names_sheet",
        "treatment_plasmid_plasmid_base_code",
        "treatment_rna_rna_base_code",
    ]
    for c in inj_cols:
        if c not in df.columns:
            df[c] = ""

    df["v3_injected_mgco_codes"] = (
        df[inj_cols]
        .astype("string")
        .fillna("")
        .agg("|".join, axis=1)
        .apply(lambda s: "|".join(parse_mgco_codes(norm_str(s))))
    )

    df["v3_pdqm_basecodes"] = df["v2_genotype_base_codes"].apply(lambda s: "|".join(parse_pdqm_codes(s)))
    df["v3_allele_nicknames"] = df["v2_genotype_allele_codes"].apply(lambda s: "|".join(parse_allele_nicknames(s)))

    pairs = []
    for i, r in df.iterrows():
        pdqms = parse_pdqm_codes(r["v2_genotype_base_codes"])
        nicks = parse_allele_nicknames(r["v2_genotype_allele_codes"])
        if len(pdqms) == 0 or len(nicks) == 0:
            pairs.append([])
            continue
        if len(pdqms) != len(nicks):
            pairs.append([])
            continue
        pairs.append(list(zip(pdqms, nicks)))

    df["v3_fk_resolve_status"] = ""
    df["v3_resolved_alleles_fk"] = ""
    df["v3_genotype_cache_fk"] = ""
    df["v3_genotype_code_fk"] = ""

    with eng.begin() as cx:
        for idx, plist in enumerate(pairs):
            if not plist:
                df.at[idx, "v3_fk_resolve_status"] = "no_pairing"
                continue
            resolved: list[tuple[str,int]] = []
            ok = True
            for base, nick in plist:
                row = cx.execute(text("""
                  SELECT allele_number
                  FROM public.transgene_alleles
                  WHERE transgene_base_code = :b
                    AND allele_nickname = :n
                """), {"b": base, "n": str(nick)}).fetchone()
                if not row:
                    ok = False
                    break
                resolved.append((base, int(row[0])))
            if not ok:
                df.at[idx, "v3_fk_resolve_status"] = "nickname_not_found"
                continue

            df.at[idx, "v3_fk_resolve_status"] = "ok"
            df.at[idx, "v3_resolved_alleles_fk"] = "|".join([f"{b}:{n}" for b,n in resolved])
            geno_str = make_geno_cache_string_fk(resolved)
            df.at[idx, "v3_genotype_cache_fk"] = geno_str
            df.at[idx, "v3_genotype_code_fk"] = gcode(geno_str)

    out_cols = [
        "bruker_roi_id",
        "experiment_folder",
        "dataset_slug",
        "roi_dir",
        "db_clutch_code",
        "db_treated_clutch_code",
        "db_treatment_code",
        "db_genotype_code",
        "v2_genotype_base_codes",
        "v2_genotype_allele_codes",
        "v3_pdqm_basecodes",
        "v3_allele_nicknames",
        "v3_injected_mgco_codes",
        "v3_fk_resolve_status",
        "v3_resolved_alleles_fk",
        "v3_genotype_cache_fk",
        "v3_genotype_code_fk",
    ]
    out_cols = [c for c in out_cols if c in df.columns]
    df[out_cols].to_csv(OUT, index=False)
    print("wrote", OUT, "rows:", len(df))

if __name__ == "__main__":
    main()
