from __future__ import annotations

from pathlib import Path
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[3]
V4_WORK = REPO_ROOT / "seed_kits" / "legacy_wrangling_v4" / "working"

SLUG_RULES = V4_WORK / "slug_marker_rules_v4.csv"

def _nonempty(x) -> bool:
    if x is None:
        return False
    s = str(x).strip()
    return s != "" and s.lower() not in ("nan", "none", "na", "n/a", "<na>")

def _blank(x) -> bool:
    return not _nonempty(x)

def apply(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    for c in [
        "dataset_slug_norm",
        "treatment_rna_base_codes",
        "treatment_plasmid_base_codes",
        "genotype_base_codes",
        "genotype_allele_codes",
    ]:
        if c not in df.columns:
            df[c] = pd.NA

    if not SLUG_RULES.exists():
        print(f"[OVR slug_rules] missing {SLUG_RULES} (skip)")
        return df

    rules = pd.read_csv(SLUG_RULES, low_memory=False).fillna("")
    rules.columns = [str(c).strip() for c in rules.columns]

    need_cols = [
        "dataset_slug_norm",
        "treatment_rna_base_codes",
        "treatment_plasmid_base_codes",
        "genotype_base_codes",
        "genotype_allele_codes",
        "rule_locked",
    ]
    miss = [c for c in need_cols if c not in rules.columns]
    if miss:
        raise SystemExit(f"[STOP] slug rules missing columns: {miss} in {SLUG_RULES}")

    rules["dataset_slug_norm"] = rules["dataset_slug_norm"].astype(str).str.strip().str.lower()
    rules = rules[rules["dataset_slug_norm"].astype(str).str.strip().ne("")].copy()
    rules["rule_locked"] = rules["rule_locked"].astype(str).str.strip().str.lower().isin(["1","t","true","y","yes"])

    rmap = {}
    for r in rules.itertuples(index=False):
        slug = str(getattr(r, "dataset_slug_norm")).strip().lower()
        rmap[slug] = {
            "treatment_rna_base_codes": str(getattr(r, "treatment_rna_base_codes")).strip(),
            "treatment_plasmid_base_codes": str(getattr(r, "treatment_plasmid_base_codes")).strip(),
            "genotype_base_codes": str(getattr(r, "genotype_base_codes")).strip(),
            "genotype_allele_codes": str(getattr(r, "genotype_allele_codes")).strip(),
            "rule_locked": bool(getattr(r, "rule_locked")),
        }

    slugs = df["dataset_slug_norm"].astype(str).str.strip().str.lower()

    n_fill_trna = n_fill_tpl = n_fill_gb = n_fill_ga = 0

    for slug, rule in rmap.items():
        mask = slugs.str.endswith(slug)
        if not int(mask.sum()):
            continue

        if rule["treatment_rna_base_codes"]:
            m2 = mask & df["treatment_rna_base_codes"].map(_blank)
            n = int(m2.sum())
            if n:
                df.loc[m2, "treatment_rna_base_codes"] = rule["treatment_rna_base_codes"]
                n_fill_trna += n

        if rule["treatment_plasmid_base_codes"]:
            m2 = mask & df["treatment_plasmid_base_codes"].map(_blank)
            n = int(m2.sum())
            if n:
                df.loc[m2, "treatment_plasmid_base_codes"] = rule["treatment_plasmid_base_codes"]
                n_fill_tpl += n

        if rule["genotype_base_codes"]:
            m2 = mask & df["genotype_base_codes"].map(_blank)
            n = int(m2.sum())
            if n:
                df.loc[m2, "genotype_base_codes"] = rule["genotype_base_codes"]
                n_fill_gb += n

        if rule["genotype_allele_codes"]:
            m2 = mask & df["genotype_allele_codes"].map(_blank)
            n = int(m2.sum())
            if n:
                df.loc[m2, "genotype_allele_codes"] = rule["genotype_allele_codes"]
                n_fill_ga += n

    print(f"[OVR slug_rules] filled_treatment_rna_base_codes={n_fill_trna}")
    print(f"[OVR slug_rules] filled_treatment_plasmid_base_codes={n_fill_tpl}")
    print(f"[OVR slug_rules] filled_genotype_base_codes={n_fill_gb}")
    print(f"[OVR slug_rules] filled_genotype_allele_codes={n_fill_ga}")

    return df
