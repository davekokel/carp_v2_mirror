from __future__ import annotations

import sys
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

# bootstrap repo root
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from carp_app.etl.util import get_engine_from_env  # noqa: E402
from carp_app.etl.code_normalization import normalize_base_code  # noqa: E402
from carp_app.config.seed_kits import LEGACY_WORKING, LEGACY_FINAL  # noqa: E402

PARENT_ALLELES_CSV      = LEGACY_WORKING / "legacy_parent_alleles.csv"
CLUTCHES_CSV            = LEGACY_FINAL   / "legacy_clutches.csv"
DEBUG_PARENT_MAP_CSV    = LEGACY_WORKING / "legacy_parent_match_debug_v3.csv"
UNMAPPED_PARENTS_CSV    = LEGACY_WORKING / "legacy_parent_to_fish_unmapped_v3.csv"
OVERRIDES_CSV           = LEGACY_WORKING / "legacy_parent_manual_overrides.csv"


def _is_casper_rnf(name: Optional[str]) -> bool:
    if not name:
        return False
    s = str(name).strip().lower().replace(" ", "")
    return "casper/rnf" in s


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


def _build_parent_to_fish_map_from_legacy(
    df_parent: pd.DataFrame,
    df_alleles: pd.DataFrame,
    df_casper: pd.DataFrame,
) -> Dict[str, str]:
    """
    df_parent: legacy_parent_alleles.csv
      - legacy_parent_name
      - transgene_base_code (already normalized)
      - allele_nickname
    """
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
        parent_name = str(row.get("legacy_parent_name", "")).strip()
        raw_base = str(row.get("transgene_base_code", "")).strip()
        allele_raw = str(row.get("allele_nickname", "")).strip()

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
                chosen = _choose_earliest_fish(
                    df_casper.rename(columns={"id": "fish_id"})
                )
                if chosen is not None:
                    f_id, f_code = chosen
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
                "legacy_parent_name": parent_name,
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
    DEBUG_PARENT_MAP_CSV.parent.mkdir(parents=True, exist_ok=True)
    df_debug.to_csv(DEBUG_PARENT_MAP_CSV, index=False)
    print(f"Parent → (base, allele_nickname) mappings: {len(df_debug)}")

    df_unmapped = df_debug[df_debug["mapped_fish_id"].isna()].copy()
    df_unmapped.to_csv(UNMAPPED_PARENTS_CSV, index=False)
    print(
        f"Wrote unmapped legacy parents to: {UNMAPPED_PARENTS_CSV} "
        f"(rows: {len(df_unmapped)})"
    )

    return mapping


def _load_manual_overrides(engine: Engine) -> Dict[str, str]:
    """
    Read legacy_parent_manual_overrides.csv and map legacy_parent_name -> fish_id
    using override_fish_code.
    """
    if not OVERRIDES_CSV.exists():
        print(f"[INFO] No manual overrides file found at {OVERRIDES_CSV}; skipping overrides.")
        return {}

    df = pd.read_csv(OVERRIDES_CSV)
    if df.empty:
        print(f"[INFO] Manual overrides file {OVERRIDES_CSV} is empty; skipping overrides.")
        return {}

    df = df.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]
    if "legacy_parent_name" not in df.columns or "override_fish_code" not in df.columns:
        print(f"[WARN] Manual overrides {OVERRIDES_CSV} missing legacy_parent_name/override_fish_code; skipping overrides.")
        return {}

    df = df.dropna(subset=["override_fish_code"])
    df["legacy_parent_name"] = df["legacy_parent_name"].astype(str).str.strip()
    df["override_fish_code"] = df["override_fish_code"].astype(str).str.strip()
    df = df[df["override_fish_code"] != ""]
    if df.empty:
        print(f"[INFO] No non-empty override_fish_code rows in {OVERRIDES_CSV}; skipping overrides.")
        return {}

    codes = sorted(set(df["override_fish_code"].tolist()))
    with engine.begin() as cx:
        df_fish = pd.read_sql(
            text(
                "SELECT id, fish_code FROM public.fish_instance WHERE fish_code = ANY(:codes)"
            ),
            cx,
            params={"codes": codes},
        )

    fish_map = {
        str(row["fish_code"]): str(row["id"])
        for _, row in df_fish.iterrows()
    }

    override_map: Dict[str, str] = {}
    missing_codes: List[str] = []

    for _, row in df.iterrows():
        parent_name = row["legacy_parent_name"]
        code = row["override_fish_code"]
        fid = fish_map.get(code)
        if not fid:
            missing_codes.append(code)
            continue
        override_map[parent_name] = fid

    print(f"[INFO] Manual overrides loaded: {len(override_map)} parent(s) mapped.")
    if missing_codes:
        uniq_missing = sorted(set(missing_codes))
        print(f"[WARN] Override fish_code(s) not found in fish_instance: {', '.join(uniq_missing)}")

    return override_map


def load_breeding_legacy(engine: Engine) -> dict:
    """
    Use legacy_parent_alleles.csv and legacy_clutches.csv to populate
    public.crosses and public.clutches.

    - One cross per unique (mom_genotype_text, dad_genotype_text).
    - Each clutch row maps to its cross_id via those labels.
    - Manual overrides (legacy_parent_manual_overrides.csv) take precedence.
    """
    if not PARENT_ALLELES_CSV.exists():
        raise FileNotFoundError(f"legacy_parent_alleles.csv not found: {PARENT_ALLELES_CSV}")
    if not CLUTCHES_CSV.exists():
        raise FileNotFoundError(f"legacy_clutches.csv not found: {CLUTCHES_CSV}")

    print(f"[INFO] Reading parent alleles: {PARENT_ALLELES_CSV}")
    df_parent = pd.read_csv(PARENT_ALLELES_CSV)
    print(f"[INFO] Reading legacy clutches: {CLUTCHES_CSV}")
    df_clutches = pd.read_csv(CLUTCHES_CSV, parse_dates=["clutch_date"])

    df_parent = df_parent.copy()
    df_parent.columns = [str(c).strip().lower() for c in df_parent.columns]
    df_clutches = df_clutches.copy()
    df_clutches.columns = [str(c).strip().lower() for c in df_clutches.columns]

    # Load manual overrides first
    overrides = _load_manual_overrides(engine)

    df_alleles = _fetch_alleles_with_fish(engine)
    if df_alleles.empty:
        print("WARNING: No transgene_alleles + fish_instance links in DB; all crosses/clutches will be skipped.")
        return {
            "crosses_inserted": 0,
            "crosses_skipped": 0,
            "clutches_inserted": 0,
            "clutches_skipped": len(df_clutches),
        }

    df_casper = _fetch_casper_fish(engine)
    print(f"[INFO] casper fish_instance candidates: {len(df_casper)}")

    # Automatic mapping from alleles + casper fallback
    parent_to_fish_auto = _build_parent_to_fish_map_from_legacy(df_parent, df_alleles, df_casper)

    # Apply overrides on top (overrides win)
    parent_to_fish: Dict[str, str] = parent_to_fish_auto.copy()
    parent_to_fish.update(overrides)

    crosses_inserted = 0
    crosses_skipped = 0
    clutches_inserted = 0
    clutches_skipped = 0

    # cache cross ids per (mom_label, dad_label)
    cross_ids: Dict[Tuple[str, str], str] = {}

    with engine.begin() as cx:
        # For now, clear legacy crosses/clutches
        cx.execute(text("TRUNCATE TABLE public.clutches, public.crosses;"))

        for _, crow in df_clutches.iterrows():
            mom_label = str(crow.get("mom_genotype_text", "")).strip()
            dad_label = str(crow.get("dad_genotype_text", "")).strip()
            clutch_code = str(crow.get("clutch_code", "")).strip()
            clutch_date = crow.get("clutch_date")
            notes = str(crow.get("notes", "")).strip() or None

            # Must have date for clutches schema
            if pd.isna(clutch_date):
                clutches_skipped += 1
                continue

            female_id = parent_to_fish.get(mom_label)
            male_id = parent_to_fish.get(dad_label)

            if not female_id or not male_id:
                crosses_skipped += 1
                clutches_skipped += 1
                continue

            pair_key = (mom_label, dad_label)
            cross_id = cross_ids.get(pair_key)

            if cross_id is None:
                # create a cross_run_code
                idx = len(cross_ids) + 1
                cross_run_code = f"LG_X_{idx:03d}"

                res = cx.execute(
                    text(
                        """
                        INSERT INTO public.crosses (cross_run_code, female_fish_id, male_fish_id, cross_date, notes)
                        VALUES (:code, :female_id, :male_id, :cross_date, :notes)
                        ON CONFLICT (cross_run_code) DO UPDATE
                          SET female_fish_id = EXCLUDED.female_fish_id,
                              male_fish_id   = EXCLUDED.male_fish_id,
                              cross_date     = EXCLUDED.cross_date,
                              notes          = EXCLUDED.notes
                        RETURNING id
                        """
                    ),
                    {
                        "code": cross_run_code,
                        "female_id": female_id,
                        "male_id": male_id,
                        "cross_date": clutch_date.date(),
                        "notes": None,
                    },
                )
                row = res.fetchone()
                if not row:
                    crosses_skipped += 1
                    clutches_skipped += 1
                    continue
                cross_id = row[0]
                cross_ids[pair_key] = cross_id
                crosses_inserted += 1

            cx.execute(
                text(
                    """
                    INSERT INTO public.clutches (clutch_code, cross_id, clutch_date, notes)
                    VALUES (:code, :cross_id, :clutch_date, :notes)
                    """
                ),
                {
                    "code": clutch_code or None,
                    "cross_id": cross_id,
                    "clutch_date": clutch_date.date(),
                    "notes": notes,
                },
            )
            clutches_inserted += 1

    return {
        "crosses_inserted": crosses_inserted,
        "crosses_skipped": crosses_skipped,
        "clutches_inserted": clutches_inserted,
        "clutches_skipped": clutches_skipped,
    }


def main() -> int:
    print(f"DB_URL={os.getenv('DB_URL')}")
    engine = get_engine_from_env()
    summary = load_breeding_legacy(engine)
    print("Summary:", summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
