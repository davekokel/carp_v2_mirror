from __future__ import annotations
from pathlib import Path
import re
import pandas as pd
import math

IN_CSV = Path("seed_kits/legacy_wrangling_v3/working/output_from_linking_v5.csv")
OUT_DIR = Path("seed_kits/legacy_wrangling_v3/working/qc_hint_mining")
OUT_DIR.mkdir(parents=True, exist_ok=True)

FOUND_RE = re.compile(r"/(Aang_Foundation|Korra_Foundation)/([^/]+)/(.*)$", re.IGNORECASE)

def nonempty(x) -> bool:
    if x is None:
        return False
    if isinstance(x, float) and pd.isna(x):
        return False
    s = str(x).strip()
    return s != "" and s.lower() not in ("nan", "none", "na", "n/a")

def split_roi_dir(roi_dir: str) -> dict:
    if not nonempty(roi_dir):
        return {"foundation": None, "experiment_folder": None, "fish_folder": None, "roi_folder": None}
    s = str(roi_dir)
    m = FOUND_RE.search(s)
    if not m:
        return {"foundation": None, "experiment_folder": None, "fish_folder": None, "roi_folder": None}
    foundation = "aang" if m.group(1).lower().startswith("aang") else "korra"
    experiment_folder = m.group(2)
    rest = m.group(3).strip("/")
    parts = rest.split("/")
    fish_folder = parts[0] if len(parts) >= 1 else None
    roi_folder = "/".join(parts[1:]) if len(parts) >= 2 else None
    return {"foundation": foundation, "experiment_folder": experiment_folder, "fish_folder": fish_folder, "roi_folder": roi_folder}

TOKEN_RE = re.compile(r"[A-Za-z0-9]+")

def tokens_from_text(x) -> list[str]:
    if not nonempty(x):
        return []
    s = str(x).lower()
    s = s.replace("-", "_")
    s = s.replace("/", "_")
    toks = TOKEN_RE.findall(s)
    toks = [t for t in toks if t and not t.isdigit()]
    return toks

def grams(tokens: list[str], n: int) -> list[str]:
    if n <= 1:
        return tokens
    if len(tokens) < n:
        return []
    return ["_".join(tokens[i:i+n]) for i in range(len(tokens)-n+1)]

def explode_hints(df: pd.DataFrame, src_col: str, src_name: str) -> pd.DataFrame:
    rows = []
    for roi_dir, txt in zip(df["roi_dir"].astype(str), df[src_col]):
        toks = tokens_from_text(txt)
        g1 = grams(toks, 1)
        g2 = grams(toks, 2)
        g3 = grams(toks, 3)
        allg = g1 + g2 + g3
        for tok in allg:
            rows.append((roi_dir, src_name, tok))
    out = pd.DataFrame(rows, columns=["roi_dir", "src", "token"])
    return out

def pick_truth_columns(df: pd.DataFrame) -> list[str]:
    preferred = [
        "all_fluor_organelles",
        "all_unique_organelles",
        "genotype_base_codes",
        "genotype_allele_codes",
        "treatment_rna_rna_base_code",
        "treatment_plasmid_plasmid_base_code",
        "Unique Targets",
        "Unique Targets with blanks",
        "ZF female genotype",
        "ZF male genotype",
    ]
    return [c for c in preferred if c in df.columns]

def make_truth_labels(df: pd.DataFrame, col: str) -> pd.Series:
    s = df[col]
    if s.dtype == "O" or str(s.dtype).startswith("string"):
        v = s.fillna("").astype(str).str.strip()
        v = v.replace({"nan": "", "None": "", "<NA>": ""})
        return (v != "")
    return s.notna()

def lift(p_token_and_truth: float, p_token: float, p_truth: float) -> float:
    if p_token <= 0 or p_truth <= 0:
        return 0.0
    return p_token_and_truth / (p_token * p_truth)

def main() -> None:
    df = pd.read_csv(IN_CSV, low_memory=False)
    if "roi_dir" not in df.columns:
        raise SystemExit("missing roi_dir")

    parts = df["roi_dir"].astype(str).apply(split_roi_dir).apply(pd.Series)
    for c in parts.columns:
        df[c] = parts[c]

    if "roi_name" not in df.columns:
        df["roi_name"] = pd.NA

    hint_sources = [
        ("roi_folder", "roi_folder"),
        ("experiment_folder", "experiment_folder"),
        ("roi_name", "roi_name"),
        ("roi_dir", "roi_dir"),
    ]
    hint_sources = [(c, n) for c, n in hint_sources if c in df.columns]

    expl = []
    for c, name in hint_sources:
        expl.append(explode_hints(df, c, name))
    hints = pd.concat(expl, ignore_index=True)
    hints = hints.dropna(subset=["token"])
    hints["token"] = hints["token"].astype(str)
    hints = hints[hints["token"].str.len() >= 3]

    tok_counts = (
        hints.drop_duplicates(["roi_dir", "src", "token"])
        .groupby(["src", "token"])
        .size()
        .reset_index(name="n_rois")
        .sort_values(["n_rois", "src", "token"], ascending=[False, True, True])
    )
    tok_counts.to_csv(OUT_DIR / "token_counts_by_source.csv", index=False)

    truth_cols = pick_truth_columns(df)
    truth_summary_rows = []
    for col in truth_cols:
        truth_summary_rows.append((col, int(make_truth_labels(df, col).sum())))
    pd.DataFrame(truth_summary_rows, columns=["truth_col", "n_true"]).to_csv(OUT_DIR / "truth_cols_present.csv", index=False)

    base = df[["roi_dir"]].copy()
    base["roi_dir"] = base["roi_dir"].astype(str)

    per_roi_tokens = (
        hints.drop_duplicates(["roi_dir", "token"])
        .groupby("roi_dir")["token"]
        .apply(lambda s: sorted(set(s.tolist())))
        .reset_index(name="tokens")
    )

    df2 = base.merge(per_roi_tokens, on="roi_dir", how="left")
    df2["tokens"] = df2["tokens"].apply(lambda x: x if isinstance(x, list) else [])

    n_rois = len(df2)

    assoc_rows = []
    if truth_cols:
        token_presence = {}
        for toks in df2["tokens"]:
            for t in toks:
                token_presence[t] = token_presence.get(t, 0) + 1

        for col in truth_cols:
            truth = make_truth_labels(df, col).astype(int).values
            n_truth = int(truth.sum())
            if n_truth == 0:
                continue
            roi_truth = pd.DataFrame({"roi_dir": df["roi_dir"].astype(str), "truth": truth}).drop_duplicates("roi_dir")
            roi_truth = df2.merge(roi_truth, on="roi_dir", how="left")
            roi_truth["truth"] = roi_truth["truth"].fillna(0).astype(int)

            for t, n_tok in token_presence.items():
                if n_tok < 5:
                    continue
                both = 0
                for toks, tr in zip(roi_truth["tokens"], roi_truth["truth"]):
                    if tr == 1 and t in toks:
                        both += 1
                p_tok = n_tok / n_rois
                p_tr = n_truth / n_rois
                p_both = both / n_rois
                l = lift(p_both, p_tok, p_tr)
                if both >= 3 and l >= 2.0:
                    assoc_rows.append((col, t, n_tok, n_truth, both, l))

    assoc = pd.DataFrame(assoc_rows, columns=["truth_col", "token", "n_rois_with_token", "n_rois_truth_true", "n_rois_both", "lift"])
    assoc = assoc.sort_values(["lift", "n_rois_both", "truth_col", "token"], ascending=[False, False, True, True])
    assoc.to_csv(OUT_DIR / "token_truth_associations.csv", index=False)

    top_tokens = tok_counts.groupby("src").head(50)
    top_tokens.to_csv(OUT_DIR / "top_tokens_by_source.csv", index=False)

    print("WROTE", OUT_DIR / "token_counts_by_source.csv")
    print("WROTE", OUT_DIR / "top_tokens_by_source.csv")
    print("WROTE", OUT_DIR / "truth_cols_present.csv")
    print("WROTE", OUT_DIR / "token_truth_associations.csv")
    print("N_ROIS", n_rois)
    print("N_UNIQUE_TOKENS", int(hints["token"].nunique()))

if __name__ == "__main__":
    main()
