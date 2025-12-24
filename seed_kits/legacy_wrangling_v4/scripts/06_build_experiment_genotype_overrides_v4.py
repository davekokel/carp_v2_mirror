from __future__ import annotations

from pathlib import Path
import re
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[3]
V4_WORK = REPO_ROOT / "seed_kits" / "legacy_wrangling_v4" / "working"

IN_ENRICHED = V4_WORK / "legacy_imaging_annotations_for_db_v9.csv"
OUT_OVERRIDES = V4_WORK / "experiment_genotype_overrides_v4.tsv"
OUT_AMBIG = V4_WORK / "experiment_genotype_overrides_v4_ambiguous.tsv"

_SPLIT = re.compile(r"[|,;]+")

def _nonempty(x) -> bool:
    if x is None:
        return False
    if isinstance(x, float) and pd.isna(x):
        return False
    s = str(x).strip()
    return s != "" and s.lower() not in ("nan", "none", "na", "n/a", "<na>")

def _norm_pipe(v) -> str:
    if not _nonempty(v):
        return ""
    parts = [p.strip() for p in _SPLIT.split(str(v)) if p.strip()]
    parts = sorted(dict.fromkeys(parts))
    return "|".join(parts)

def main() -> None:
    if not IN_ENRICHED.exists():
        raise SystemExit(f"[STOP] missing: {IN_ENRICHED}")

    df = pd.read_csv(IN_ENRICHED, low_memory=False)
    df.columns = [str(c).strip() for c in df.columns]

    need = ["roi_experiment_folder", "genotype_base_codes", "genotype_allele_codes"]
    miss = [c for c in need if c not in df.columns]
    if miss:
        raise SystemExit(f"[STOP] IN_ENRICHED missing columns: {miss}")

    df = df.copy()
    df["roi_experiment_folder"] = df["roi_experiment_folder"].astype(str).str.strip()
    df["geno_base_norm"] = df["genotype_base_codes"].map(_norm_pipe)
    df["geno_alle_norm"] = df["genotype_allele_codes"].map(_norm_pipe)

    g = (
        df.groupby("roi_experiment_folder", as_index=False)
          .agg(
              n_rois=("roi_experiment_folder", "count"),
              n_with_base=("geno_base_norm", lambda s: int((s.astype(str).str.strip() != "").sum())),
              n_distinct_base=("geno_base_norm", lambda s: int(len({x for x in s.astype(str).tolist() if x.strip()}))),
              base_values=("geno_base_norm", lambda s: " || ".join(sorted({x for x in s.astype(str).tolist() if x.strip()}))),
              allele_values=("geno_alle_norm", lambda s: " || ".join(sorted({x for x in s.astype(str).tolist() if x.strip()}))),
          )
    )

    ok = g[(g["n_with_base"] > 0) & (g["n_distinct_base"] == 1)].copy()
    amb = g[(g["n_with_base"] > 0) & (g["n_distinct_base"] > 1)].copy()

    if len(ok):
        ok["genotype_base_codes_override"] = ok["base_values"]
        ok["genotype_allele_codes_override"] = ok["allele_values"]
        ok = ok[[
            "roi_experiment_folder",
            "genotype_base_codes_override",
            "genotype_allele_codes_override",
            "n_rois",
            "n_with_base",
        ]].sort_values(["roi_experiment_folder"], kind="mergesort")

    if len(amb):
        amb = amb.sort_values(["n_distinct_base", "roi_experiment_folder"], ascending=[False, True], kind="mergesort")

    OUT_OVERRIDES.parent.mkdir(parents=True, exist_ok=True)
    ok.to_csv(OUT_OVERRIDES, sep="\t", index=False)
    amb.to_csv(OUT_AMBIG, sep="\t", index=False)

    print("[OK] wrote", OUT_OVERRIDES, "rows", len(ok))
    print("[OK] wrote", OUT_AMBIG, "rows", len(amb))
    if len(amb):
        print("[WARN] ambiguous experiments need manual resolution (see file)")

if __name__ == "__main__":
    main()
