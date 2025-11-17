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
    RNA_PREVIEW_XLSX,
    LEGACY_WORKING,
    LEGACY_FINAL,
    STANDARD_SEEDKIT,
)

ALIAS_CSV = LEGACY_WORKING / "legacy_rna_aliases.csv"
LEGACY_RNAS_CSV = LEGACY_FINAL / "legacy_rnas.csv"


def build_legacy_rna_aliases() -> pd.DataFrame:
    """
    Read Unique_injected_rna__preview_dqm.xlsx (no header row) and build a flat alias table:

        injected_rna, rna_base_code, rna_base_code_norm, notes
    """
    xlsx = RNA_PREVIEW_XLSX
    if not xlsx.exists():
        raise FileNotFoundError(f"RNA preview XLSX not found: {xlsx}")

    print(f"[INFO] Reading RNA preview: {xlsx}")
    raw = pd.read_excel(xlsx, header=None)
    if raw.empty:
        return pd.DataFrame(columns=["injected_rna", "rna_base_code", "rna_base_code_norm", "notes"])

    df = raw.iloc[:, :2].copy()
    df.columns = ["injected_rna", "rna_base_code"]
    df["injected_rna"] = df["injected_rna"].astype(str).str.strip()
    df["rna_base_code"] = df["rna_base_code"].astype(str).str.strip()

    rows: List[Dict[str, str]] = []

    for _, row in df.iterrows():
        inj = row["injected_rna"]
        bases_raw = str(row.get("rna_base_code", "") or "")
        if not inj and not bases_raw:
            continue

        # split on commas if present, otherwise treat the whole string as one code
        if "," in bases_raw:
            parts = [p.strip() for p in bases_raw.split(",")]
        else:
            parts = [bases_raw.strip()] if bases_raw.strip() else []

        for part in parts:
            if not part:
                continue
            norm = normalize_base_code(part)
            rows.append(
                {
                    "injected_rna": inj,
                    "rna_base_code": part,
                    "rna_base_code_norm": norm,
                    "notes": "",
                }
            )

    alias_df = pd.DataFrame(rows)
    LEGACY_WORKING.mkdir(parents=True, exist_ok=True)
    print(f"[INFO] Writing legacy RNA aliases to: {ALIAS_CSV}")
    alias_df.to_csv(ALIAS_CSV, index=False)
    print(f"[INFO] alias rows={len(alias_df)}")

    return alias_df


def build_legacy_rnas(alias_df: pd.DataFrame) -> pd.DataFrame:
    """
    Build a standard-style legacy_rnas.csv:

        rna_base_code, name, notes
    """
    alias_df = alias_df.copy()
    alias_df["rna_base_code_norm"] = alias_df["rna_base_code_norm"].astype(str).str.strip()
    alias_df["injected_rna"] = alias_df["injected_rna"].astype(str).str.strip()

    std_rna_csv = STANDARD_SEEDKIT / "rnas.csv"
    if std_rna_csv.exists():
        std = pd.read_csv(std_rna_csv)
        std = std.copy()
        std.columns = [str(c).strip().lower() for c in std.columns]

        if "rna_base_code" in std.columns:
            std["base_norm"] = std["rna_base_code"].astype(str).str.strip().apply(normalize_base_code)
        elif "code" in std.columns:
            std["base_norm"] = std["code"].astype(str).str.strip().apply(normalize_base_code)
        else:
            print(f"[WARN] Standard rnas {std_rna_csv} has no rna_base_code or code; skipping enrichment.")
            std = pd.DataFrame(columns=["base_norm"])
    else:
        print(f"[WARN] Standard rnas CSV not found at {std_rna_csv}; building legacy_rnas from aliases only.")
        std = pd.DataFrame(columns=["base_norm"])

    records: List[dict] = []

    for base_norm, sub in alias_df.groupby("rna_base_code_norm"):
        if not base_norm:
            continue

        name = ""
        notes = ""

        if not std.empty:
            std_match = std[std["base_norm"] == base_norm]
            if not std_match.empty:
                row = std_match.iloc[0]
                if "name" in row.index:
                    name = str(row.get("name", "") or "")
                elif "nickname" in row.index:
                    name = str(row.get("nickname", "") or "")
                if "notes" in row.index:
                    notes = str(row.get("notes", "") or "")

        if not name:
            inj_names = sorted({p for p in sub["injected_rna"].dropna().tolist() if p})
            if inj_names:
                name = inj_names[0]
                if len(inj_names) > 1:
                    extra = "; ".join(inj_names[1:])
                    if notes:
                        notes = f"{notes} | other injected labels: {extra}"
                    else:
                        notes = f"other injected labels: {extra}"

        records.append(
            {
                "rna_base_code": base_norm,
                "name": name,
                "notes": notes,
            }
        )

    rna_df = pd.DataFrame(records)
    rna_df = rna_df.sort_values(["rna_base_code"]).reset_index(drop=True)

    LEGACY_FINAL.mkdir(parents=True, exist_ok=True)
    print(f"[INFO] Writing legacy rnas to: {LEGACY_RNAS_CSV}")
    rna_df.to_csv(LEGACY_RNAS_CSV, index=False)
    print(f"[INFO] legacy rna rows={len(rna_df)}")

    return rna_df


def main() -> None:
    alias_df = build_legacy_rna_aliases()
    if alias_df.empty:
        print("[WARN] No aliases generated; skipping legacy rnas.")
        return
    build_legacy_rnas(alias_df)
    print("[DONE] legacy rnas wrangling complete.")


if __name__ == "__main__":
    main()
