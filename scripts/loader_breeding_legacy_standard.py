from __future__ import annotations

import sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from carp_app.etl.loaders import get_engine_from_env
from carp_app.etl.code_normalization import normalize_base_code


ROOT = Path(__file__).resolve().parents[1]
STD_ROOT = ROOT / "carp_app" / "seed_kits" / "standard_from_legacy"


def _is_casper_rnf(name: Optional[str]) -> bool:
    if not name:
        return False
    s = str(name).strip().lower().replace(" ", "")
    return "casper/rnf" in s


def _load_parent_csv(std_root: Path) -> pd.DataFrame:
    parent_path = std_root / "Unique_parent_names__mom_dad_combined__preview_.csv"
    if not parent_path.exists():
        raise FileNotFoundError(
            f"Legacy parent CSV not found: {parent_path}"
        )
    df = pd.read_csv(parent_path)
    required = ["parent_fish_name", "plasmid_base_code", "allele"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Parent CSV missing columns: {missing}")
    return df


def _load_crosses_clutches(std_root: Path) -> Tuple[pd.DataFrame, pd.DataFrame]:
    crosses_csv = std_root / "crosses_standard_from_legacy.csv"
    clutches_csv = std_root / "clutches_standard_from_legacy.csv"

    if not crosses_csv.exists():
        raise FileNotFoundError(f"Crosses CSV not found: {crosses_csv}")
    if not clutches_csv.exists():
        raise FileNotFoundError(f"Clutches CSV not found: {clutches_csv}")

    df_crosses = pd.read_csv(crosses_csv)
    df_clutches = pd.read_csv(clutches_csv)

    crosses_required = [
        "legacy_pair_id",
        "cross_run_code",
        "dataset",
        "female_legacy_label",
        "male_legacy_label",
    ]
    clutches_required = [
        "legacy_pair_id",
        "cross_run_code",
        "dataset",
        "clutch_code",
        "clutch_date",
    ]

    missing_c = [c for c in crosses_required if c not in df_crosses.columns]
    if missing_c:
        raise ValueError(f"Crosses CSV missing columns: {missing_c}")

    missing_cl = [c for c in clutches_required if c not in df_clutches.columns]
    if missing_cl:
        raise ValueError(f"Clutches CSV missing columns: {missing_cl}")

    return df_crosses, df_clutches


def _fetch_alleles_with_fish(engine: Engine) -> pd.DataFrame:
    with engine.begin() as cx:
        df = pd.read_sql(
            text(
                """
                SELECT
                  ta.transgene_base_code,
                  ta.allele_number,
                  ta.allele_nickname,
                  f.id   AS fish_id,
                  f.fish_code,
                  f.nickname,
                  f.birthday
                FROM public.transgene_alleles ta
                JOIN public.join_fish_transgene_alleles jfta
                  ON jfta.transgene_base_code = ta.transgene_base_code
                 AND jfta.allele_number       = ta.allele_number
                JOIN public.fish_instance f
                  ON f.id = jfta.fish_id
                """
            ),
            cx,
        )
    return df


def _fetch_casper_fish(engine: Engine) -> pd.DataFrame:
    with engine.begin() as cx:
        df = pd.read_sql(
            text(
                """
                SELECT
                  f.id,
                  f.fish_code,
                  f.genetic_background,
                  f.birthday
                FROM public.fish_instance f
                WHERE f.genetic_background = 'casper'
                ORDER BY f.birthday NULLS LAST, f.fish_code
                """
            ),
            cx,
        )
    return df


def _choose_earliest_fish(df: pd.DataFrame) -> Optional[Tuple[str, str]]:
    if df.empty:
        return None
    sub = df[["fish_id", "fish_code", "birthday"]].drop_duplicates()
    sub = sub.sort_values(["birthday", "fish_code"], na_position="last")
    row = sub.iloc[0]
    return str(row["fish_id"]), str(row["fish_code"])


def _build_parent_to_fish_map(
    df_parent: pd.DataFrame,
    df_alleles: pd.DataFrame,
    df_casper: pd.DataFrame,
    std_root: Path,
) -> Dict[str, str]:
    df_alleles = df_alleles.copy()
    df_alleles["norm_base_code"] = df_alleles["transgene_base_code"].map(
        normalize_base_code
    )
    df_alleles["allele_nickname"] = (
        df_alleles["allele_nickname"].fillna("").astype(str).str.strip()
    )

    df_casper = df_casper.copy()

    parent_records: List[dict] = []
    mapping: Dict[str, str] = {}

    for _, row in df_parent.iterrows():
        parent_name = (
            str(row["parent_fish_name"]).strip()
            if pd.notna(row["parent_fish_name"])
            else ""
        )
        raw_base = (
            str(row["plasmid_base_code"]).strip()
            if pd.notna(row["plasmid_base_code"])
            else ""
        )
        allele_raw = (
            str(row["allele"]).strip() if pd.notna(row["allele"]) else ""
        )

        if not parent_name:
            continue

        norm_base = normalize_base_code(raw_base)
        allele_nick = allele_raw.strip()

        n_alleles = 0
        n_fish = 0
        fish_id: Optional[str] = None
        chosen_fish_code: Optional[str] = None

        if _is_casper_rnf(parent_name):
            if not df_casper.empty:
                f_id, f_code = _choose_earliest_fish(
                    df_casper.rename(columns={"id": "fish_id"})
                )
                if f_id is not None:
                    fish_id = f_id
                    chosen_fish_code = f_code
                    n_alleles = 0
                    n_fish = len(df_casper)
                else:
                    n_alleles = 0
                    n_fish = 0
            else:
                n_alleles = 0
                n_fish = 0
        else:
            if not norm_base or not allele_nick:
                matching = df_alleles.iloc[0:0]
            else:
                mask = (df_alleles["norm_base_code"] == norm_base) & (
                    df_alleles["allele_nickname"] == allele_nick
                )
                matching = df_alleles.loc[mask]

            n_alleles = (
                matching[["norm_base_code", "allele_number"]]
                .drop_duplicates()
                .shape[0]
            )
            n_fish = matching["fish_id"].nunique()

            if n_alleles > 0 and n_fish >= 1:
                chosen = _choose_earliest_fish(matching)
                if chosen is not None:
                    f_id, f_code = chosen
                    fish_id = f_id
                    chosen_fish_code = f_code

        parent_records.append(
            {
                "parent_fish_name": parent_name,
                "raw_plasmid_base_code": raw_base,
                "norm_plasmid_base_code": norm_base,
                "allele_nickname": allele_nick,
                "n_matching_alleles": n_alleles,
                "n_matching_fish": n_fish,
                "mapped_fish_id": fish_id,
                "mapped_fish_code": chosen_fish_code,
            }
        )

        if fish_id is not None:
            mapping[parent_name] = fish_id

    df_debug = pd.DataFrame(parent_records)
    debug_csv = std_root / "legacy_parent_match_debug_v2.csv"
    df_debug.to_csv(debug_csv, index=False)
    print(f"Parent \u2192 (base, allele_nickname) mappings: {len(df_debug)}")

    df_unmapped = df_debug[df_debug["mapped_fish_id"].isna()].copy()

    unmapped_csv = std_root / "legacy_parent_to_fish_unmapped.csv"
    df_unmapped.to_csv(unmapped_csv, index=False)
    print(
        f"Wrote unmapped legacy parents to: {unmapped_csv} "
        f"(rows: {len(df_unmapped)})"
    )

    return mapping


def load_breeding_from_legacy_standard(engine: Engine, std_root: Path) -> dict:
    std_root.mkdir(parents=True, exist_ok=True)

    df_parent = _load_parent_csv(std_root)
    df_crosses, df_clutches = _load_crosses_clutches(std_root)

    df_alleles = _fetch_alleles_with_fish(engine)
    if df_alleles.empty:
        print("WARNING: No transgene_alleles + fish_instance links in DB; all crosses will be skipped.")
        return {
            "crosses_inserted": 0,
            "crosses_skipped": len(df_crosses),
            "clutches_inserted": 0,
            "clutches_skipped": len(df_clutches),
        }

    df_casper = _fetch_casper_fish(engine)
    print(f"casper fish_instance candidates: {len(df_casper)}")

    parent_to_fish = _build_parent_to_fish_map(df_parent, df_alleles, df_casper, std_root)

    crosses_inserted = 0
    crosses_skipped = 0
    clutches_inserted = 0
    skipped_cross_codes: set[str] = set()

    with engine.begin() as cx:
        cx.execute(text("TRUNCATE TABLE public.clutches, public.crosses;"))

        for _, row in df_crosses.iterrows():
            cross_code = str(row["cross_run_code"]).strip()
            female_label = str(row["female_legacy_label"]).strip()
            male_label = str(row["male_legacy_label"]).strip()

            female_id = parent_to_fish.get(female_label)
            male_id = parent_to_fish.get(male_label)

            if not female_id or not male_id:
                crosses_skipped += 1
                skipped_cross_codes.add(cross_code)
                continue

            res = cx.execute(
                text(
                    """
                    INSERT INTO public.crosses (cross_run_code, female_fish_id, male_fish_id)
                    VALUES (:code, :female_id, :male_id)
                    ON CONFLICT (cross_run_code) DO UPDATE
                      SET female_fish_id = EXCLUDED.female_fish_id,
                          male_fish_id   = EXCLUDED.male_fish_id
                    RETURNING id
                    """
                ),
                {
                    "code": cross_code,
                    "female_id": female_id,
                    "male_id": male_id,
                },
            )
            cross_id_row = res.fetchone()
            if not cross_id_row:
                crosses_skipped += 1
                skipped_cross_codes.add(cross_code)
                continue
            cross_id = cross_id_row[0]
            crosses_inserted += 1

            matching_clutches = df_clutches[
                df_clutches["cross_run_code"].astype(str).str.strip() == cross_code
            ]
            for _, crow in matching_clutches.iterrows():
                clutch_code = str(crow["clutch_code"]).strip()
                clutch_date = str(crow["clutch_date"]).strip() or None
                notes = str(crow.get("notes", "")).strip() or None

                cx.execute(
                    text(
                        """
                        INSERT INTO public.clutches (clutch_code, cross_id, clutch_date, notes)
                        VALUES (:code, :cross_id, :clutch_date, :notes)
                        """
                    ),
                    {
                        "code": clutch_code,
                        "cross_id": cross_id,
                        "clutch_date": clutch_date,
                        "notes": notes,
                    },
                )
                clutches_inserted += 1

    skipped_mask = (
        df_clutches["cross_run_code"].astype(str).str.strip().isin(skipped_cross_codes)
    )
    clutches_skipped = int(skipped_mask.sum())

    return {
        "crosses_inserted": crosses_inserted,
        "crosses_skipped": crosses_skipped,
        "clutches_inserted": clutches_inserted,
        "clutches_skipped": clutches_skipped,
    }


def main() -> int:
    print(f"DB_URL={os.getenv('DB_URL')}")
    engine = get_engine_from_env()
    summary = load_breeding_from_legacy_standard(engine, STD_ROOT)
    print("Summary:", summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
