from __future__ import annotations

import pandas as pd

BASE = "pDQM063"
ALLELE_NICK = "314"

def _nonempty(x) -> bool:
    if x is None:
        return False
    s = str(x).strip()
    return s != "" and s.lower() not in ("nan", "none", "na", "n/a", "<na>")

def apply(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    cols = {c: c for c in df.columns}

    if "genotype_base_codes" not in cols:
        df["genotype_base_codes"] = ""
    if "genotype_allele_codes" not in cols:
        df["genotype_allele_codes"] = ""

    slug = df.get("dataset_slug_norm", pd.Series([""] * len(df))).astype(str).str.strip().str.lower()
    exp  = df.get("experiment_name", pd.Series([""] * len(df))).astype(str).str.strip().str.lower()

    is_skitt = slug.str.contains("skitt", na=False) | exp.str.contains("skitt", na=False)

    gb_blank = df["genotype_base_codes"].astype(str).str.strip().eq("")
    ga_blank = df["genotype_allele_codes"].astype(str).str.strip().eq("")

    target = is_skitt & gb_blank
    n = int(target.sum())
    if n:
        df.loc[target, "genotype_base_codes"] = BASE
        df.loc[target & ga_blank, "genotype_allele_codes"] = ALLELE_NICK

    print(f"[OVR skittlez_default_pdqm63_314] filled genotype_base_codes={n}")
    return df
