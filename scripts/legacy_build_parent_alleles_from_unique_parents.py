from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, List

import pandas as pd

# bootstrap repo root
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from carp_app.etl.util import normalize_base_code  # noqa: E402
from carp_app.config.seed_kits import (            # noqa: E402
    LEGACY_RAW,
    LEGACY_WORKING,
    PARENT_PREVIEW_XLSX,
)

OUT_CSV = LEGACY_WORKING / "legacy_parent_alleles.csv"


def build_legacy_parent_alleles() -> pd.DataFrame:
    """
    Read Unique_parent_names__mom_dad_combined__preview_dqm.xlsx (no header row)
    and emit legacy_parent_alleles.csv with columns:

        legacy_parent_name, transgene_base_code, allele_nickname,
        zygosity, confidence, notes
    """
    xlsx = PARENT_PREVIEW_XLSX
    if not xlsx.exists():
        raise FileNotFoundError(f"Parent preview XLSX not found: {xlsx}")

    print(f"[INFO] Reading parent preview: {xlsx}")
    # No header row: first row is data
    raw = pd.read_excel(xlsx, header=None)
    if raw.empty:
        return pd.DataFrame(columns=["legacy_parent_name", "transgene_base_code", "allele_nickname", "zygosity", "confidence", "notes"])

    # Use the first three columns
    df = raw.iloc[:, :3].copy()
    df.columns = ["parent_fish_name", "plasmid_base_code", "allele"]

    df["parent_fish_name"] = df["parent_fish_name"].astype(str).str.strip()
    df["plasmid_base_code"] = df["plasmid_base_code"].astype(str).str.strip()
    df["allele"] = df["allele"].astype(str).str.strip()

    # Drop rows with no parent name
    df = df[df["parent_fish_name"] != ""].reset_index(drop=True)

    out = pd.DataFrame()
    out["legacy_parent_name"] = df["parent_fish_name"]
    out["transgene_base_code"] = df["plasmid_base_code"].apply(
        lambda s: normalize_base_code(s) if isinstance(s, str) else ""
    )
    out["allele_nickname"] = df["allele"]

    out["zygosity"] = ""
    out["confidence"] = ""
    out["notes"] = ""

    mask_has = (out["transgene_base_code"].str.len() > 0) & (out["allele_nickname"].str.len() > 0)
    dropped = len(out) - int(mask_has.sum())
    if dropped:
        print(f"[INFO] Dropping {dropped} row(s) with empty transgene_base_code or allele_nickname.")
    out = out[mask_has].reset_index(drop=True)

    LEGACY_WORKING.mkdir(parents=True, exist_ok=True)
    print(f"[INFO] Writing legacy parent alleles to: {OUT_CSV}")
    out.to_csv(OUT_CSV, index=False)
    print(f"[INFO] parent alleles rows={len(out)}")

    return out


def main() -> None:
    build_legacy_parent_alleles()
    print("[DONE] legacy_parent_alleles build complete.")


if __name__ == "__main__":
    main()
