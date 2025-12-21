from __future__ import annotations

import re
import pandas as pd

SHEET = "seed_kits/legacy_wrangling_v3/working/imaging_sheet_augmented_v3.csv"
ROI_CSV = "seed_kits/legacy_wrangling_v3/working/legacy_imaging_annotations_for_db_v9_compat.csv"

OUT_OK = "seed_kits/legacy_wrangling_v3/working/exp_treatment_signatures.csv"
OUT_BAD = "seed_kits/legacy_wrangling_v3/working/exp_treatment_signatures_ambiguous.csv"

RE_SHEET = re.compile(r"(Aang_Foundation|Korra_Foundation|Exploratory_fish)[/\\](\d{8}[^/\\]+)", re.I)
RE_ROI = re.compile(r"/(Aang_Foundation|Korra_Foundation|Exploratory_fish)/(\d{8}[^/]+)/", re.I)

_WS_RE = re.compile(r"\s+")
_PARENS_RE = re.compile(r"\(.*?\)")
_MGCO_DIGITS_RE = re.compile(r"\bmgco[-_ ]?0*([0-9]+)\b", re.I)

def _path_norm(x) -> str:
    if x is None:
        return ""
    s = str(x).strip()
    if s.lower() in ("nan", "none"):
        return ""
    return s

def _canon_foundation(name: str) -> str:
    n = (name or "").strip()
    lo = n.lower()
    if lo == "aang_foundation":
        return "Aang_Foundation"
    if lo == "korra_foundation":
        return "Korra_Foundation"
    if lo == "exploratory_fish":
        return "Exploratory_fish"
    return n

def key_from_sheet(path) -> str:
    m = RE_SHEET.search(_path_norm(path))
    if not m:
        return ""
    return f"{_canon_foundation(m.group(1))}/{m.group(2)}"

def key_from_roi_dir(path) -> str:
    m = RE_ROI.search(_path_norm(path))
    if not m:
        return ""
    return f"{_canon_foundation(m.group(1))}/{m.group(2)}"

def _strip_parens(s: str) -> str:
    return _PARENS_RE.sub("", s or "")

def _norm_token(x) -> str:
    # Accept anything (float NaN from pandas, etc.)
    if x is None:
        return ""
    if isinstance(x, float) and pd.isna(x):
        return ""
    s = str(x).strip().lower()
    if not s or s in ("nan", "none"):
        return ""

    s = _strip_parens(s)
    s = _WS_RE.sub(" ", s).strip()

    # Normalize separators but do NOT destroy ':' structure
    s = s.replace("—", "-").replace("–", "-")

    # Canonicalize common fluor shorthand used in sheet-tokens
    # (These are deterministic rewrites, not DB guessing.)
    s = re.sub(r"\bmstaygold\b", "msg", s)
    s = re.sub(r"\btdmstaygold\b", "tdmsg", s)
    s = re.sub(r"\bjf\s*-?\s*0*635\b", "jf-635", s)

    # Normalize common basecode styles (mgco/pdqm/hc) with or without dash/zero padding
    s = re.sub(r"\bmgco\s*-?\s*0*([0-9]+)\b", r"mgco-\1", s)
    s = re.sub(r"\bpdqm\s*-?\s*0*([0-9]+)\b", r"pdqm-\1", s)
    s = re.sub(r"\bhc\s*-?\s*0*([0-9]+)\b", r"hc-\1", s)

    # Handful of *known* sheet tokens → canonical base_code (deterministic)
    # These are from verified DB lookups you already ran:
    s = re.sub(r"\bmsg:sec61b\b", "mgco-4", s)
    s = re.sub(r"\bmscarlet3[- ]?s2:h2b\b", "pdqm-117", s)
    s = re.sub(r"\btdmchilada:pcna\b", "pdqm-26", s)
    s = re.sub(r"\bef1a:mgold2s\b", "pdqm-140", s)
    s = re.sub(r"\bphic-nls\b", "pdqm-130", s)

    return s


def _split_construct_tokens(x) -> list[str]:
    """
    Split ONLY on explicit list separators (comma/pipe/semicolon).
    Do NOT split on whitespace; whitespace inside tokens is common in the sheet.
    """
    s = _norm_token(x)
    if not s:
        return []

    # Turn explicit separators into commas, then split
    s = s.replace("|", ",").replace(";", ",")
    parts = [p.strip() for p in s.split(",") if p.strip()]

    out: list[str] = []
    seen = set()
    for p in parts:
        p = _norm_token(p)
        if not p or p in seen:
            continue
        seen.add(p)
        out.append(p)
    return sorted(out)

def _split_dye_tokens(x: str) -> list[str]:
    """
    For dyes: keep multiword dye names intact if present, but normalize JF-635 variants.
    We split on comma/pipe/semicolon only (NOT whitespace).
    """
    s = _norm_token(x)
    if not s:
        return []
    s = s.replace("|", ",").replace(";", ",")
    parts = [p.strip() for p in s.split(",") if p.strip()]
    out: list[str] = []
    seen = set()
    for p in parts:
        p = _norm_token(p)
        if not p:
            continue
        # normalize JF 635 / jf635 / jf-635 -> jf-635
        p2 = re.sub(r"\s+", "-", p)
        p2 = re.sub(r"[^a-z0-9-]+", "-", p2)
        p2 = re.sub(r"-{2,}", "-", p2).strip("-")
        if p2 in ("jf-635", "jf635"):
            p2 = "jf-635"
        if p2 in seen:
            continue
        seen.add(p2)
        out.append(p2)
    return sorted(out)

def sig(plas: list[str], rnas: list[str], dyes: list[str]) -> str:
    return f"plasmids={','.join(plas)}|rnas={','.join(rnas)}|dyes={','.join(dyes)}"

def main() -> None:
    df_sheet = pd.read_csv(SHEET, low_memory=False)
    df_sheet.columns = [c.strip() for c in df_sheet.columns]

    if "Data location" not in df_sheet.columns:
        raise SystemExit(f"[STOP] imaging sheet missing 'Data location' column; found {list(df_sheet.columns)}")

    df_sheet["dataset_key"] = df_sheet["Data location"].map(key_from_sheet)
    df_sheet = df_sheet[df_sheet["dataset_key"] != ""].copy()

    for col in ("additional plasmids injected", "additional mRNAs injected", "additonal dye and chemicals"):
        if col not in df_sheet.columns:
            df_sheet[col] = ""

    df_sheet["pla"] = df_sheet["additional plasmids injected"].map(_split_construct_tokens)
    df_sheet["rna"] = df_sheet["additional mRNAs injected"].map(_split_construct_tokens)
    df_sheet["dye"] = df_sheet["additonal dye and chemicals"].map(_split_dye_tokens)
    df_sheet["signature"] = df_sheet.apply(lambda r: sig(r.pla, r.rna, r.dye), axis=1)

    sig_counts = (
        df_sheet.groupby("dataset_key")["signature"]
        .nunique()
        .reset_index(name="n_signatures")
    )
    bad_keys = set(sig_counts.loc[sig_counts["n_signatures"] > 1, "dataset_key"].astype(str).tolist())

    df_roi = pd.read_csv(ROI_CSV, low_memory=False)
    df_roi.columns = [c.strip() for c in df_roi.columns]

    if "roi_dir" not in df_roi.columns or "bruker_roi_id" not in df_roi.columns:
        raise SystemExit(f"[STOP] ROI compat CSV missing roi_dir/bruker_roi_id; found {list(df_roi.columns)}")

    df_roi["dataset_key"] = df_roi["roi_dir"].map(key_from_roi_dir)
    df_roi = df_roi[df_roi["dataset_key"] != ""].copy()
    df_roi["bruker_roi_id"] = df_roi["bruker_roi_id"].astype(str).str.strip()

    df_units = df_sheet[["dataset_key", "signature"]].drop_duplicates()
    df_join = (
        df_roi[["bruker_roi_id", "dataset_key"]]
        .merge(df_units, on="dataset_key", how="inner")
        .drop_duplicates()
    )

    df_bad = (
        df_join[df_join["dataset_key"].isin(bad_keys)]
        .sort_values(["dataset_key", "bruker_roi_id", "signature"])
        .reset_index(drop=True)
    )
    df_ok = (
        df_join[~df_join["dataset_key"].isin(bad_keys)]
        .sort_values(["dataset_key", "signature", "bruker_roi_id"])
        .reset_index(drop=True)
    )

    df_ok.to_csv(OUT_OK, index=False)
    df_bad.to_csv(OUT_BAD, index=False)

    print("WROTE_OK", OUT_OK, "rows", len(df_ok), "dataset_keys", df_ok["dataset_key"].nunique(), "signatures", df_ok["signature"].nunique())
    print("WROTE_BAD", OUT_BAD, "rows", len(df_bad), "dataset_keys", df_bad["dataset_key"].nunique(), "signatures", df_bad["signature"].nunique())
    print("BAD_KEYS:")
    for k in sorted(bad_keys):
        print(" ", k)

if __name__ == "__main__":
    main()