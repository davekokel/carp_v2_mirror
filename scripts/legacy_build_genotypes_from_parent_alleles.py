from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd

# bootstrap repo root
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from carp_app.etl.util import normalize_base_code  # noqa: E402
from carp_app.config.seed_kits import LEGACY_WORKING, LEGACY_FINAL  # <-- add this

PARENT_ALLELES_CSV = LEGACY_WORKING / "legacy_parent_alleles.csv"
GENOTYPES_OUT      = LEGACY_FINAL / "legacy_genotypes.csv"
GENO_ALLELES_OUT   = LEGACY_FINAL / "legacy_genotype_alleles.csv"


def _build_genotype_key(base_code: str, allele_nick: str) -> Tuple[str, str, str]:
    """
    Normalize base_code and build (genotype_code, genotype_name, base_code_norm).

    We follow the pattern:
      GT_LEG_<BASE_WITH_UNDERSCORES>_<ALLELE>

    where BASE_WITH_UNDERSCORES is normalize_base_code(base).replace('-', '_').
    """
    base_norm = normalize_base_code(base_code)
    base_slug = base_norm.replace("-", "_")
    allele = str(allele_nick).strip()
    gcode = f"GT_LEG_{base_slug}_{allele}" if base_slug and allele else ""
    gname = f"{base_norm} {allele}" if base_norm and allele else ""
    return gcode, gname, base_norm


def build_legacy_genotypes(parent_df: pd.DataFrame) -> pd.DataFrame:
    """
    Build legacy_genotypes.csv from parent→allele rows.

    For each unique (transgene_base_code, allele_nickname), we create one genotype.
    Notes summarise which legacy_parent_name values contributed.
    """
    # Normalize columns
    df = parent_df.copy()
    df["transgene_base_code"] = df["transgene_base_code"].astype(str).str.strip()
    df["allele_nickname"] = df["allele_nickname"].astype(str).str.strip()
    df["legacy_parent_name"] = df["legacy_parent_name"].astype(str).str.strip()
    df["zygosity"] = df.get("zygosity", "").astype(str).str.strip()

    # Group by base+allele
    grouped: Dict[Tuple[str, str], Dict[str, object]] = {}

    for _, row in df.iterrows():
        base = row["transgene_base_code"]
        allele = row["allele_nickname"]
        parent = row["legacy_parent_name"]

        if not base or not allele:
            continue

        key = (base, allele)
        if key not in grouped:
            gcode, gname, base_norm = _build_genotype_key(base, allele)
            grouped[key] = {
                "genotype_code": gcode,
                "genotype_name": gname,
                "genetic_background": "casper",
                "source_system": "legacy",
                "base_code_norm": base_norm,
                "parents": set(),  # type: ignore[assignment]
            }

        grouped[key]["parents"].add(parent)  # type: ignore[index]

    records: List[Dict[str, str]] = []
    for (base, allele), info in grouped.items():
        parents = sorted(p for p in info["parents"] if p)  # type: ignore[index]
        notes = ""
        if parents:
            # Limit length to something reasonable
            joined = "; ".join(parents)
            if len(joined) > 512:
                joined = joined[:509] + "..."
            notes = f"parents: {joined}"

        records.append(
            {
                "genotype_code": info["genotype_code"],        # type: ignore[index]
                "genotype_name": info["genotype_name"],        # type: ignore[index]
                "genetic_background": info["genetic_background"],  # type: ignore[index]
                "source_system": info["source_system"],        # type: ignore[index]
                "notes": notes,
            }
        )

    geno_df = pd.DataFrame(records)
    # Drop any empty genotype_code rows just in case
    geno_df = geno_df[geno_df["genotype_code"].astype(bool)].copy()
    geno_df = geno_df.sort_values(["genotype_code"]).reset_index(drop=True)
    return geno_df


def build_legacy_genotype_alleles(parent_df: pd.DataFrame, geno_df: pd.DataFrame) -> pd.DataFrame:
    """
    Build legacy_genotype_alleles.csv with the standard contract:

      genotype_code,transgene_base_code,allele_nickname,zygosity

    Each parent row becomes one genotype_allele row, with genotype_code
    determined only by (base, allele), independent of which parent carried it.
    """
    df = parent_df.copy()
    df["transgene_base_code"] = df["transgene_base_code"].astype(str).str.strip()
    df["allele_nickname"] = df["allele_nickname"].astype(str).str.strip()
    df["zygosity"] = df.get("zygosity", "").astype(str).str.strip()

    # Build mapping (base, allele) -> genotype_code
    key_to_code: Dict[Tuple[str, str], str] = {}
    for _, row in geno_df.iterrows():
        base, allele = row["genotype_name"].split(" ", 1) if " " in row["genotype_name"] else ("", "")
        if base and allele:
            key_to_code[(base, allele)] = row["genotype_code"]

    rows: List[Dict[str, str]] = []
    for _, row in df.iterrows():
        base_raw = row["transgene_base_code"]
        allele = row["allele_nickname"]
        if not base_raw or not allele:
            continue
        base_norm = normalize_base_code(base_raw)
        key = (base_norm, allele)
        gcode = key_to_code.get(key)
        if not gcode:
            # Fallback: recompute code directly
            gcode, _, _ = _build_genotype_key(base_raw, allele)
        if not gcode:
            continue
        rows.append(
            {
                "genotype_code": gcode,
                "transgene_base_code": base_norm,
                "allele_nickname": allele,
                "zygosity": row.get("zygosity", ""),
            }
        )

    ga_df = pd.DataFrame(rows)
    ga_df = ga_df.sort_values(["genotype_code", "transgene_base_code", "allele_nickname"]).reset_index(drop=True)
    return ga_df


def main() -> None:
    if not PARENT_ALLELES_CSV.exists():
        raise FileNotFoundError(f"Parent→alleles working CSV not found: {PARENT_ALLELES_CSV}")

    print(f"[INFO] Reading legacy parent alleles: {PARENT_ALLELES_CSV}")
    parent_df = pd.read_csv(PARENT_ALLELES_CSV)
    if parent_df.empty:
        raise RuntimeError(f"{PARENT_ALLELES_CSV} is empty")

    # Build genotype tables
    geno_df = build_legacy_genotypes(parent_df)
    ga_df = build_legacy_genotype_alleles(parent_df, geno_df)

    LEGACY_FINAL.mkdir(parents=True, exist_ok=True)

    print(f"[INFO] Writing legacy genotypes to: {GENOTYPES_OUT}")
    geno_df.to_csv(GENOTYPES_OUT, index=False)

    print(f"[INFO] Writing legacy genotype_alleles to: {GENO_ALLELES_OUT}")
    ga_df.to_csv(GENO_ALLELES_OUT, index=False)

    print(f"[DONE] genotypes={len(geno_df)}, genotype_alleles={len(ga_df)}")


if __name__ == "__main__":
    main()
