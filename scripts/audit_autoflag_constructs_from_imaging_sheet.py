from __future__ import annotations

from pathlib import Path
import re
import sys
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

SHEET = ROOT / "seed_kits" / "legacy_wrangling_v2" / "raw" / "2025-11-21-220012-imaging_sheet.xlsx"
CONSTRUCTS = ROOT / "seed_kits" / "2025-11-15-121231-autoload" / "constructs_plasmid.csv"
OUT = CONSTRUCTS.with_suffix(".autoflags.csv")

RNA_COL = "additional mRNAs injected"
PLASMID_COL = "additional plasmids injected"

TOK_RE = re.compile(r"\b([A-Za-z]{2,6})[-_ ]?0*(\d{1,4})\b")

def canon_token(s: str) -> str | None:
    s = (s or "").strip()
    if not s:
        return None
    m = TOK_RE.search(s)
    if not m:
        return None
    pref = m.group(1).lower()
    num = int(m.group(2))
    return f"{pref}-{num}"

def extract_tokens(cell: object) -> set[str]:
    if cell is None:
        return set()
    s = str(cell).strip()
    if not s or s.lower() in ("nan", "none", "na", "n/a", "<na>"):
        return set()
    toks: set[str] = set()
    for part in re.split(r"[;,|]+", s):
        part = part.strip()
        if not part:
            continue
        part2 = re.sub(r"\(.*?\)", "", part).strip()
        t = canon_token(part2)
        if t:
            toks.add(t)
            continue
        t2 = canon_token(part)
        if t2:
            toks.add(t2)
    return toks

def as_bool01(v: object) -> int:
    s = "" if v is None else str(v).strip().lower()
    return 1 if s in ("1", "true", "t", "yes", "y") else 0

def main() -> None:
    if not SHEET.exists():
        raise SystemExit(f"[STOP] imaging sheet not found: {SHEET}")
    if not CONSTRUCTS.exists():
        raise SystemExit(f"[STOP] constructs CSV not found: {CONSTRUCTS}")

    dfc = pd.read_csv(CONSTRUCTS, low_memory=False)
    for col in ["plasmid_code", "used_for_injection_plasmid", "used_for_injection_rna", "used_for_injection_crispr"]:
        if col not in dfc.columns:
            raise SystemExit(f"[STOP] constructs CSV missing required column: {col}")

    dfc["plasmid_code_norm"] = dfc["plasmid_code"].astype(str).str.strip().map(canon_token)
    if dfc["plasmid_code_norm"].isna().any():
        bad = dfc[dfc["plasmid_code_norm"].isna()][["plasmid_code"]].drop_duplicates().head(50)
        raise SystemExit(f"[STOP] could not normalize some plasmid_code values. Examples:\n{bad.to_string(index=False)}")

    df_sheet = pd.read_excel(SHEET, engine=None)
    cols = [c for c in df_sheet.columns]
    if RNA_COL not in cols:
        raise SystemExit(f"[STOP] imaging sheet missing column: {RNA_COL}")
    if PLASMID_COL not in cols:
        raise SystemExit(f"[STOP] imaging sheet missing column: {PLASMID_COL}")

    rna_tokens: set[str] = set()
    plasmid_tokens: set[str] = set()

    for v in df_sheet[RNA_COL].tolist():
        rna_tokens |= extract_tokens(v)

    for v in df_sheet[PLASMID_COL].tolist():
        plasmid_tokens |= extract_tokens(v)

    known = set(dfc["plasmid_code_norm"].tolist())
    rna_unknown = sorted([t for t in rna_tokens if t not in known])
    plasmid_unknown = sorted([t for t in plasmid_tokens if t not in known])

    dfc["used_for_injection_plasmid"] = dfc["used_for_injection_plasmid"].apply(as_bool01)
    dfc["used_for_injection_rna"] = dfc["used_for_injection_rna"].apply(as_bool01)

    dfc["__set_rna"] = dfc["plasmid_code_norm"].isin(rna_tokens).astype(int)
    dfc["__set_plasmid"] = dfc["plasmid_code_norm"].isin(plasmid_tokens).astype(int)

    before_rna = dfc["used_for_injection_rna"].sum()
    before_plasmid = dfc["used_for_injection_plasmid"].sum()

    dfc["used_for_injection_rna"] = ((dfc["used_for_injection_rna"] == 1) | (dfc["__set_rna"] == 1)).astype(int)
    dfc["used_for_injection_plasmid"] = ((dfc["used_for_injection_plasmid"] == 1) | (dfc["__set_plasmid"] == 1)).astype(int)

    after_rna = dfc["used_for_injection_rna"].sum()
    after_plasmid = dfc["used_for_injection_plasmid"].sum()

    changed_rna = dfc[(dfc["__set_rna"] == 1) & (dfc["used_for_injection_rna"] == 1)][["plasmid_code", "plasmid_code_norm"]].copy()
    changed_plasmid = dfc[(dfc["__set_plasmid"] == 1) & (dfc["used_for_injection_plasmid"] == 1)][["plasmid_code", "plasmid_code_norm"]].copy()

    out = dfc.drop(columns=["plasmid_code_norm", "__set_rna", "__set_plasmid"])
    out.to_csv(OUT, index=False)

    print("[OK] wrote", OUT)
    print("[SUMMARY] imaging_sheet_rna_tokens", len(rna_tokens), "plasmid_tokens", len(plasmid_tokens))
    print("[SUMMARY] constructs_rna_flag_before", int(before_rna), "after", int(after_rna), "delta", int(after_rna - before_rna))
    print("[SUMMARY] constructs_plasmid_flag_before", int(before_plasmid), "after", int(after_plasmid), "delta", int(after_plasmid - before_plasmid))
    print("[SUMMARY] rna_tokens_unmapped", len(rna_unknown))
    if rna_unknown:
        print("  ", ", ".join(rna_unknown[:50]) + ("" if len(rna_unknown) <= 50 else " ..."))
    print("[SUMMARY] plasmid_tokens_unmapped", len(plasmid_unknown))
    if plasmid_unknown:
        print("  ", ", ".join(plasmid_unknown[:50]) + ("" if len(plasmid_unknown) <= 50 else " ..."))

if __name__ == "__main__":
    main()
