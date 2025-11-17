from __future__ import annotations

import sys
from pathlib import Path
from typing import Tuple

import pandas as pd
from sqlalchemy import text

# repo bootstrap (so carp_app imports work)
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from carp_app.etl.loaders import get_engine_from_env  # type: ignore


NA_VALUES = {"", "nan", "na", "n/a", "none", "null", "?"}


def _norm_base_code(raw: str | float | None) -> str:
    """
    Normalize legacy plasmid_base_code into the canonical transgene_base_code
    format used in v7 transgenes/transgene_alleles.

    Examples:
      pDQM005  -> PDQM-5
      PDQM005  -> PDQM-5
      PDQM-5   -> PDQM-5
      MGCO01   -> MGCO-1
      MGCO-35  -> MGCO-35

    For non-matching things (e.g. 'SWINBURNE', 'PIGLET 14A') we just
    return the uppercased, stripped token so the mismatch is explicit.
    """
    if raw is None:
        return ""
    s = str(raw).strip()
    if not s:
        return ""
    if s.lower() in NA_VALUES:
        return ""

    s_up = s.upper().strip()

    import re

    m = re.match(r"^([A-Z]+)[\-_]?(0*)(\d+)$", s_up)
    if m:
        prefix, _zeros, num = m.groups()
        num_int = int(num)
        return f"{prefix}-{num_int}"

    # already like MGCO-35 or HC-9 etc, or weird things like SWINBURNE
    return s_up


def _norm_allele_nickname(raw: str | float | None) -> Tuple[str, bool]:
    """
    Normalize legacy allele nickname.

    Returns (normalized_value, is_multi):
      - normalized_value: '' if missing / NA, else the cleaned token
      - is_multi: True if the raw string contained ',' or ';' (multi-allele row)

    We do NOT attempt to parse into canonical allele_number; we match
    against transgene_alleles.allele_nickname which already stores the
    legacy nicknames (301, 315, 336, etc.).
    """
    if raw is None:
        return "", False
    s = str(raw).strip()
    if not s or s.lower() in NA_VALUES:
        return "", False

    # Treat commas/semicolons as multi-allele markers; we don't auto-split here
    if "," in s or ";" in s:
        return s, True

    return s, False


def main() -> int:
    engine = get_engine_from_env()
    legacy_dir = ROOT / "carp_app" / "seed_kits" / "standard_from_legacy"

    # ---- locate legacy parent CSV ------------------------------------------
    parent_csv = legacy_dir / "Unique_parent_names__mom_dad_combined__preview_.csv"
    if not parent_csv.exists():
        # fall back to pattern; helpful if the file was renamed with a date
        matches = list(legacy_dir.glob("Unique_parent_names__mom_dad*"))
        if not matches:
            print(
                "No legacy parent CSV found matching 'Unique_parent_names__mom_dad*.csv' in:\n"
                f"  {legacy_dir}\n"
                "Files present:"
            )
            for p in sorted(legacy_dir.iterdir()):
                print(f"  - {p.name}")
            return 0
        parent_csv = matches[0]

    print(f"Using legacy parent CSV: {parent_csv}")

    df_parent = pd.read_csv(parent_csv)
    cols = [c.lower().strip() for c in df_parent.columns]

    # figure out column names
    def _find_col(candidates):
        for c in candidates:
            if c.lower() in cols:
                return df_parent.columns[cols.index(c.lower())]
        return None

    parent_name_col = _find_col(["parent_fish_name", "legacy_parent_name", "parent_name"])
    plasmid_col = _find_col(["plasmid_base_code", "base_code", "plasmid"])
    allele_col = _find_col(["allele_nickname", "allele"])

    if not parent_name_col or not plasmid_col or not allele_col:
        print("Could not infer parent_name / plasmid_base_code / allele column names.")
        print("Columns in CSV:", list(df_parent.columns))
        return 1

    # ---- load transgene_alleles for matching -------------------------------
    with engine.begin() as cx:
        df_alleles = pd.read_sql(
            text(
                """
                SELECT
                  transgene_base_code,
                  allele_number,
                  allele_nickname
                FROM public.transgene_alleles
                """
            ),
            cx,
        )

    if df_alleles.empty:
        print("No rows in public.transgene_alleles; nothing to match against.")
        return 0

    # normalize alleles table (so we can match against normalized base + nick)
    df_alleles["base_norm"] = df_alleles["transgene_base_code"].apply(_norm_base_code)
    df_alleles["allele_norm"], _ = zip(
        *[ _norm_allele_nickname(v) for v in df_alleles["allele_nickname"] ]
    )

    # index for quick lookup
    grouped_alleles = df_alleles.groupby(["base_norm", "allele_norm"])

    mapped_rows = []
    unmapped_rows = []

    # ---- walk legacy parent rows -------------------------------------------
    for _, row in df_parent.iterrows():
        legacy_name = str(row[parent_name_col]).strip() if pd.notna(row[parent_name_col]) else ""
        raw_base = row[plasmid_col]
        raw_allele = row[allele_col]

        if not legacy_name:
            continue

        base_norm = _norm_base_code(raw_base)
        allele_norm, is_multi = _norm_allele_nickname(raw_allele)

        # reasons we consider this unmapped up-front
        if not base_norm:
            unmapped_rows.append(
                {
                    "legacy_parent_name": legacy_name,
                    "plasmid_base_code_raw": raw_base,
                    "allele_raw": raw_allele,
                    "base_norm": base_norm,
                    "allele_norm": allele_norm,
                    "reason": "missing_or_weird_plasmid_base_code",
                }
            )
            continue

        if not allele_norm:
            unmapped_rows.append(
                {
                    "legacy_parent_name": legacy_name,
                    "plasmid_base_code_raw": raw_base,
                    "allele_raw": raw_allele,
                    "base_norm": base_norm,
                    "allele_norm": allele_norm,
                    "reason": "missing_allele_nickname",
                }
            )
            continue

        if is_multi:
            unmapped_rows.append(
                {
                    "legacy_parent_name": legacy_name,
                    "plasmid_base_code_raw": raw_base,
                    "allele_raw": raw_allele,
                    "base_norm": base_norm,
                    "allele_norm": allele_norm,
                    "reason": "multi_allele_in_single_row",
                }
            )
            continue

        key = (base_norm, allele_norm)
        if key not in grouped_alleles.groups:
            unmapped_rows.append(
                {
                    "legacy_parent_name": legacy_name,
                    "plasmid_base_code_raw": raw_base,
                    "allele_raw": raw_allele,
                    "base_norm": base_norm,
                    "allele_norm": allele_norm,
                    "reason": "no_matching_transgene_alleles_in_DB",
                }
            )
            continue

        bucket = grouped_alleles.get_group(key)
        if len(bucket) > 1:
            unmapped_rows.append(
                {
                    "legacy_parent_name": legacy_name,
                    "plasmid_base_code_raw": raw_base,
                    "allele_raw": raw_allele,
                    "base_norm": base_norm,
                    "allele_norm": allele_norm,
                    "reason": "multiple_matching_transgene_alleles_in_DB",
                }
            )
            continue

        # Exactly one match → resolved
        matched = bucket.iloc[0]
        mapped_rows.append(
            {
                "legacy_parent_name": legacy_name,
                "plasmid_base_code_raw": raw_base,
                "allele_raw": raw_allele,
                "base_norm": base_norm,
                "allele_norm": allele_norm,
                "transgene_base_code": matched["transgene_base_code"],
                "allele_number": int(matched["allele_number"]),
            }
        )

    df_mapped = pd.DataFrame(mapped_rows)
    df_unmapped = pd.DataFrame(unmapped_rows)

    unmapped_csv = legacy_dir / "legacy_parent_alleles_unmapped.csv"
    df_unmapped.to_csv(unmapped_csv, index=False)
    print(f"Wrote unmapped legacy parent alleles to: {unmapped_csv}")
    print(f"Rows: {len(df_unmapped)}")

    # If nothing mapped, we’re done
    if df_mapped.empty:
        print("No legacy parent alleles mapped to transgene_alleles; skipping genotype candidate generation.")
        return 0

    # ---- Map mapped parent alleles to existing genotypes -------------------
    with engine.begin() as cx:
        df_gj = pd.read_sql(
            text(
                """
                SELECT
                  g.id                  AS genotype_id,
                  g.genotype_code       AS genotype_code,
                  g.genotype_name       AS genotype_name,
                  g.source_system       AS source_system,
                  j.transgene_base_code AS transgene_base_code,
                  j.allele_number       AS allele_number
                FROM public.join_genotype_transgene_alleles j
                JOIN public.genotypes g
                  ON g.id = j.genotype_id
                """
            ),
            cx,
        )

    if df_gj.empty:
        print("No genotypes/join_genotype_transgene_alleles in DB; skipping genotype candidate mapping.")
        return 0

    # how many alleles per genotype (for match_ratio)
    geno_sizes = (
        df_gj.groupby("genotype_code")["allele_number"]
        .nunique()
        .rename("n_alleles_in_genotype")
    )

    # join mapped parent alleles with genotype alleles
    df_hits = df_mapped.merge(
        df_gj,
        how="inner",
        on=["transgene_base_code", "allele_number"],
        suffixes=("", "_geno"),
    )

    if df_hits.empty:
        print("No overlapping alleles between legacy parents and existing genotypes.")
        return 0

    # each row in df_hits is one shared allele; aggregate per (parent, genotype)
    grouped = (
        df_hits.groupby(
            ["legacy_parent_name", "plasmid_base_code_raw", "allele_raw", "transgene_base_code"]
        )
        .apply(
            lambda g: pd.DataFrame(
                {
                    "legacy_parent_name": [g["legacy_parent_name"].iloc[0]],
                    "plasmid_base_code_raw": [g["plasmid_base_code_raw"].iloc[0]],
                    "allele_raw": [g["allele_raw"].iloc[0]],
                    "transgene_base_code": [g["transgene_base_code"].iloc[0]],
                    "allele_number": [g["allele_number"].iloc[0]],
                    "candidate_genotype_code": [g["genotype_code"].iloc[0]],
                    "candidate_genotype_name": [g["genotype_name"].iloc[0]],
                    "candidate_source_system": [g["source_system"].iloc[0]],
                    "n_shared_alleles": [len(g)],
                }
            )
        )
        .reset_index(drop=True)
    )

    # attach n_alleles_in_genotype and match_ratio
    grouped = grouped.merge(
        geno_sizes.reset_index(),
        how="left",
        left_on="candidate_genotype_code",
        right_on="genotype_code",
    ).drop(columns=["genotype_code"])

    grouped["match_ratio"] = grouped["n_shared_alleles"] / grouped["n_alleles_in_genotype"].clip(lower=1)

    # sort so best matches per parent bubble to the top
    grouped = grouped.sort_values(
        by=["legacy_parent_name", "match_ratio", "n_shared_alleles"],
        ascending=[True, False, False],
    )

    out_csv = legacy_dir / "legacy_parent_genotype_standard_candidates.csv"
    grouped.to_csv(out_csv, index=False)
    print(f"Wrote legacy parent \u2192 standard genotype candidates to: {out_csv}")
    print(f"Rows: {len(grouped)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
