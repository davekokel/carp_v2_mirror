from __future__ import annotations

from pathlib import Path
import sys
import importlib.util
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[3]
V4_WORK = REPO_ROOT / "seed_kits" / "legacy_wrangling_v4" / "working"

IN_ALL = V4_WORK / "legacy_imaging_annotations_for_db_v9_all_rois.csv"
OUT_DB = V4_WORK / "legacy_imaging_annotations_for_db_v9.csv"

def _nonempty(x) -> bool:
    if x is None:
        return False
    s = str(x).strip()
    return s != "" and s.lower() not in ("nan", "none", "na", "n/a", "<na>")

def _load_override(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, str(path))
    if spec is None or spec.loader is None:
        raise SystemExit(f"[STOP] could not load override module: {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if not hasattr(mod, "apply"):
        raise SystemExit(f"[STOP] override missing apply(df): {path}")
    return mod

def main() -> None:
    if not IN_ALL.exists():
        raise SystemExit(f"[STOP] missing input: {IN_ALL} (run 02_enrich_v4.py first)")

    df = pd.read_csv(IN_ALL, low_memory=False)
    df.columns = [str(c).strip() for c in df.columns]

    overrides_dir = Path(__file__).resolve().parent
    override_files = sorted([p for p in overrides_dir.glob("ovr_*.py")])

    for p in override_files:
        mod = _load_override(p)
        df = mod.apply(df)

    is_test = df.get("dataset_slug_norm", pd.Series([""] * len(df))).astype(str).str.strip().str.lower().eq("analysis_test")
    has_geno = df.get("genotype_base_codes", pd.Series([""] * len(df))).map(_nonempty)
    has_ft = df.get("free_text_label", pd.Series([""] * len(df))).map(_nonempty)

    out = df.loc[(~is_test) & (has_geno | has_ft)].copy()
    out.to_csv(OUT_DB, index=False)
    print("WROTE", OUT_DB, "ROWS", len(out))

if __name__ == "__main__":
    main()
