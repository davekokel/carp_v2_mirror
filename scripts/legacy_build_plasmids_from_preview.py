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
    PLASMID_PREVIEW_XLSX,
    LEGACY_WORKING,
    LEGACY_FINAL,
    STANDARD_SEEDKIT,
)

ALIAS_CSV = LEGACY_WORKING / "legacy_plasmid_aliases.csv"
LEGACY_PLASMIDS_CSV = LEGACY_FINAL / "legacy_plasmids.csv"


def build_legacy_plasmid_aliases() -> pd.DataFrame:
    """
    Read Unique_injected_plasmid__preview_dqm.xlsx (no header row) and build a flat alias table:

        injected_plasmid, plasmid_base_code, plasmid_base_code_norm, notes
    """
    xlsx = PLASMID_PREVIEW_XLSX
    if not xlsx.exists():
        raise FileNotFoundError(f"Plasmid preview XLSX not found: {xlsx}")

    print(f"[INFO] Reading plasmid preview: {xlsx}")
    # No header row: first row is data
    raw = pd.read_excel(xlsx, header=None)
    if raw.empty:
        return pd.DataFrame(columns=["injected_plasmid", "plasmid_base_code", "plasmid_base_code_norm", "notes"])

    # Use first two columns and assign canonical names
    df = raw.iloc[:, :2].copy()
    df.columns = ["injected_plasmid", "plasmid_base_code"]
    df["injected_plasmid"] = df["injected_plasmid"].astype(str).str.strip()
    df["plasmid_base_code"] = df["plasmid_base_code"].astype(str).str.strip()

    rows: List[Dict[str, str]] = []

    for _, row in df.iterrows():
        inj = row["injected_plasmid"]
        bases_raw = str(row.get("plasmid_base_code", "") or "")
        if not inj and not bases_raw:
            continue

        parts = [p.strip() for p in bases_raw.split(",")] if bases_raw else [""]
        if not parts:
            parts = [""]

        for part in parts:
            if not part:
                continue
            norm = normalize_base_code(part)
            rows.append(
                {
                    "injected_plasmid": inj,
                    "plasmid_base_code": part,
                    "plasmid_base_code_norm": norm,
                    "notes": "",
                }
            )

    alias_df = pd.DataFrame(rows)
    LEGACY_WORKING.mkdir(parents=True, exist_ok=True)
    print(f"[INFO] Writing legacy plasmid aliases to: {ALIAS_CSV}")
    alias_df.to_csv(ALIAS_CSV, index=False)
    print(f"[INFO] alias rows={len(alias_df)}")

    return alias_df


def build_legacy_plasmids(alias_df: pd.DataFrame) -> pd.DataFrame:
    """
    Build a standard-style legacy_plasmids.csv:

        plasmid_base_code, plasmid_code, nickname, notes
    """
    alias_df = alias_df.copy()
    alias_df["plasmid_base_code_norm"] = alias_df["plasmid_base_code_norm"].astype(str).str.strip()
    alias_df["injected_plasmid"] = alias_df["injected_plasmid"].astype(str).str.strip()

    std_pl_csv = STANDARD_SEEDKIT / "plasmids.csv"
    if std_pl_csv.exists():
        std = pd.read_csv(std_pl_csv)
        std = std.copy()
        std.columns = [str(c).strip().lower() for c in std.columns]

        if "plasmid_base_code" in std.columns:
            std["base_norm"] = std["plasmid_base_code"].astype(str).str.strip().apply(normalize_base_code)
        elif "plasmid_code" in std.columns:
            std["base_norm"] = std["plasmid_code"].astype(str).str.strip().apply(normalize_base_code)
        else:
            print(f"[WARN] Standard plasmids {std_pl_csv} has no plasmid_base_code or plasmid_code; skipping enrichment.")
            std = pd.DataFrame(columns=["base_norm"])
    else:
        print(f"[WARN] Standard plasmids CSV not found at {std_pl_csv}; building legacy_plasmids from aliases only.")
        std = pd.DataFrame(columns=["base_norm"])

    records: List[dict] = []

    for base_norm, sub in alias_df.groupby("plasmid_base_code_norm"):
        if not base_norm:
            continue

        plasmid_code = base_norm.replace("-", "")
        nickname = ""
        notes = ""

        if not std.empty:
            std_match = std[std["base_norm"] == base_norm]
            if not std_match.empty:
                row = std_match.iloc[0]
                if "plasmid_code" in row.index:
                    plasmid_code = str(row.get("plasmid_code", "") or plasmid_code)
                if "nickname" in row.index:
                    nickname = str(row.get("nickname", "") or "")
                if "notes" in row.index:
                    notes = str(row.get("notes", "") or "")

        if not nickname:
            inj_names = sorted({p for p in sub["injected_plasmid"].dropna().tolist() if p})
            if inj_names:
                nickname = inj_names[0]
                if len(inj_names) > 1:
                    extra = "; ".join(inj_names[1:])
                    if notes:
                        notes = f"{notes} | other injected labels: {extra}"
                    else:
                        notes = f"other injected labels: {extra}"

        records.append(
            {
                "plasmid_base_code": base_norm,
                "plasmid_code": plasmid_code,
                "nickname": nickname,
                "notes": notes,
            }
        )

    pl_df = pd.DataFrame(records)
    pl_df = pl_df.sort_values(["plasmid_base_code"]).reset_index(drop=True)

    LEGACY_FINAL.mkdir(parents=True, exist_ok=True)
    print(f"[INFO] Writing legacy plasmids to: {LEGACY_PLASMIDS_CSV}")
    pl_df.to_csv(LEGACY_PLASMIDS_CSV, index=False)
    print(f"[INFO] legacy plasmids rows={len(pl_df)}")

    return pl_df


def main() -> None:
    alias_df = build_legacy_plasmid_aliases()
    if alias_df.empty:
        print("[WARN] No aliases generated; skipping legacy plasmids.")
        return
    build_legacy_plasmids(alias_df)
    print("[DONE] legacy plasmids wrangling complete.")


if __name__ == "__main__":
    main()
