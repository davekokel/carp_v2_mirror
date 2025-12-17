from __future__ import annotations
from pathlib import Path
import re
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[3]
IN_DIR = REPO_ROOT / "seed_kits" / "legacy_wrangling_v3" / "working" / "qc_hint_mining"
OUT_VOCAB = IN_DIR / "token_vocab_v1.csv"
OUT_SKIPPED = IN_DIR / "token_vocab_v1_skipped.csv"

def _nonempty(x) -> bool:
    if x is None:
        return False
    if isinstance(x, float) and pd.isna(x):
        return False
    s = str(x).strip()
    return s != "" and s.lower() not in ("nan", "none", "na", "n/a")

STOPWORDS = {
    "x",
    "foundation",
}
ORGANELLES = {
    "mem", "mito", "er", "cytosol", "peroxi", "lyso", "nuclear", "membrane", "organelle",
}
FLUORS = {
    "halo", "msg", "msc2", "msc3",
}
ANATOMY = {
    "tail", "tailbud", "hindbrain", "brain", "ear", "eye", "spine", "mb",
}

RE_FISH = re.compile(r"^fish\d+$", re.I)
RE_ROI = re.compile(r"^roi\d+$", re.I)
RE_HPF = re.compile(r"^\d+hpf$", re.I)

def suggest_type(tok: str) -> tuple[str, str]:
    t = tok.lower().strip()

    if not t:
        return ("", "empty")
    if t in STOPWORDS:
        return ("", "stopword")
    if RE_FISH.match(t) or RE_ROI.match(t):
        return ("", "structural_id")
    if RE_HPF.match(t):
        return ("developmental_stage", "matches ^\\d+hpf$")
    if t in ANATOMY:
        return ("anatomy", "in anatomy lexicon")
    if t in ORGANELLES:
        return ("organelle", "in organelle lexicon")
    if t in FLUORS:
        return ("fluor", "in fluor lexicon")

    if re.fullmatch(r"[a-z][a-z0-9-]*", t):
        return ("experiment_label", "default for remaining word-like tokens")

    return ("", "unclassified")

def main() -> None:
    if not IN_DIR.exists():
        raise SystemExit(f"missing input dir: {IN_DIR}")

    sources = []
    for fn in ["top_tokens_by_source.csv", "token_truth_associations.csv", "token_counts_by_source.csv"]:
        p = IN_DIR / fn
        if p.exists():
            sources.append(p)

    if not sources:
        raise SystemExit(f"no input csvs found in {IN_DIR}")

    toks: set[str] = set()
    for p in sources:
        df = pd.read_csv(p)
        if "token" not in df.columns:
            continue
        for raw in df["token"].dropna().astype(str):
            raw = raw.strip()
            if not raw:
                continue
            parts = re.split(r"[_\s]+", raw)
            for part in parts:
                part = part.strip()
                if part:
                    toks.add(part)

    rows = []
    skipped = []
    for tok in sorted(toks, key=lambda x: x.lower()):
        mt, why = suggest_type(tok)
        if mt:
            rows.append({"token": tok, "meaning_type": mt, "rationale": why})
        else:
            skipped.append({"token": tok, "reason": why})

    out = pd.DataFrame(rows)
    out.to_csv(OUT_VOCAB, index=False)

    sk = pd.DataFrame(skipped)
    sk.to_csv(OUT_SKIPPED, index=False)

    print("WROTE", OUT_VOCAB)
    print("ROWS", len(out), "N_UNIQUE_TOKENS", len(toks))
    print("MEANING_TYPE_COUNTS")
    print(out["meaning_type"].value_counts(dropna=False).to_string())
    print("WROTE", OUT_SKIPPED)
    print("SKIPPED_ROWS", len(sk))

if __name__ == "__main__":
    main()
