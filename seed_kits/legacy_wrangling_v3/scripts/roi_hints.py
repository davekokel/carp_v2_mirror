from __future__ import annotations
from pathlib import Path
import re
import pandas as pd

IN_CSV = Path("seed_kits/legacy_wrangling_v3/working/output_from_linking_v5.csv")
OUT_CSV = Path("seed_kits/legacy_wrangling_v3/working/qc_roi_hints_extract.csv")

FOUND_RE = re.compile(r"/(Aang_Foundation|Korra_Foundation)/([^/]+)/(.*)$", re.IGNORECASE)
FISH_RE = re.compile(r"fish(\d+)(?:[_-]([0-9]+)hpf)?", re.IGNORECASE)

ORG_TOKENS = [
    "er", "mito", "peroxi", "peroxisome", "lyso", "lysosome", "golgi", "endo", "endosome",
    "nuc", "nuclear", "mem", "membrane", "cytosol",
]
MARKER_TOKENS = ["lifeact", "pcna", "h2b", "tubulin", "moesin"]
FLUOR_TOKENS = ["mstaygold", "msg", "tdmscarlet3", "tdmscarlet3s2", "tdmchilada", "halo", "gfp"]

ANATOMY_TOKENS = ["tail", "hindbrain", "spine", "somite", "trunk", "heart", "eye"]

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

    return {
        "foundation": foundation,
        "experiment_folder": experiment_folder,
        "fish_folder": fish_folder,
        "roi_folder": roi_folder,
    }

def fish_hints(fish_folder: str | None) -> dict:
    if not nonempty(fish_folder):
        return {"fish_num": None, "age_hpf": None}
    m = FISH_RE.search(str(fish_folder))
    if not m:
        return {"fish_num": None, "age_hpf": None}
    fish_num = int(m.group(1)) if m.group(1) else None
    age_hpf = int(m.group(2)) if m.group(2) else None
    return {"fish_num": fish_num, "age_hpf": age_hpf}

def normalize_text(s: str) -> str:
    s = str(s).lower()
    s = s.replace("-", "_")
    s = re.sub(r"[^a-z0-9_:/]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def first_token_hit(text: str, tokens: list[str]) -> str | None:
    if not nonempty(text):
        return None
    t = normalize_text(text)
    # allow token to appear anywhere as a whole-ish word boundary in normalized space
    for tok in tokens:
        tok2 = tok.lower().replace("-", "_")
        if re.search(rf"(^|[ _:/]){re.escape(tok2)}($|[ _:/])", t):
            return tok
    return None

def main() -> None:
    df = pd.read_csv(IN_CSV, low_memory=False)
    for c in ["roi_dir", "roi_name", "date_experiment", "dataset"]:
        if c not in df.columns:
            raise SystemExit(f"missing required column: {c}")

    rows = []
    for r in df.itertuples(index=False):
        roi_dir = getattr(r, "roi_dir", None)
        roi_name = getattr(r, "roi_name", None)
        parts = split_roi_dir(roi_dir)

        # Candidate text sources (ordered by “most likely to contain semantic hints”)
        src_roi_name = roi_name
        src_experiment = parts["experiment_folder"]
        src_full = roi_dir

        organelle = (
            first_token_hit(src_roi_name, ORG_TOKENS)
            or first_token_hit(src_experiment, ORG_TOKENS)
            or first_token_hit(src_full, ORG_TOKENS)
        )
        marker = (
            first_token_hit(src_roi_name, MARKER_TOKENS)
            or first_token_hit(src_experiment, MARKER_TOKENS)
            or first_token_hit(src_full, MARKER_TOKENS)
        )
        fluor = (
            first_token_hit(src_roi_name, FLUOR_TOKENS)
            or first_token_hit(src_experiment, FLUOR_TOKENS)
            or first_token_hit(src_full, FLUOR_TOKENS)
        )
        anatomy = (
            first_token_hit(src_roi_name, ANATOMY_TOKENS)
            or first_token_hit(src_full, ANATOMY_TOKENS)
        )

        fh = fish_hints(parts["fish_folder"])

        rows.append({
            "roi_dir": roi_dir,
            "dataset": getattr(r, "dataset", None),
            "date_experiment": getattr(r, "date_experiment", None),
            **parts,
            **fh,
            "roi_name": roi_name,
            "organelle_hint": organelle,
            "marker_hint": marker,
            "fluor_hint": fluor,
            "anatomy_hint": anatomy,
        })

    out = pd.DataFrame(rows)
    out.to_csv(OUT_CSV, index=False)

    print("WROTE", OUT_CSV)
    print("ROWS", len(out), "UNIQUE_ROI_DIR", out["roi_dir"].nunique())

    print("\nTOP roi_folder (non-null) sample (first 30 distinct):")
    rf = out["roi_folder"].dropna().astype(str).unique().tolist()
    for x in sorted(rf)[:30]:
        print(x)

    for c in ["organelle_hint", "marker_hint", "fluor_hint", "anatomy_hint"]:
        print("\n", c)
        print(out[c].value_counts(dropna=False).head(25).to_string())

if __name__ == "__main__":
    main()
