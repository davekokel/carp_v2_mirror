from __future__ import annotations

import os
from typing import Dict, List, Tuple

import pandas as pd
from sqlalchemy import create_engine, text

DB_URL = os.getenv("DB_URL")


def load_mapping(csv_path: str) -> List[Tuple[str, str]]:
    """
    Load clutch_code / treatment_code pairs from the mapping CSV.

    Expected columns:
      - clutch_code
      - treatment_code
    """
    df = pd.read_csv(csv_path)

    if "clutch_code" not in df.columns or "treatment_code" not in df.columns:
        raise ValueError(f"{csv_path} must have 'clutch_code' and 'treatment_code' columns")

    pairs: List[Tuple[str, str]] = []
    for _, row in df.iterrows():
        clutch_code = str(row["clutch_code"] or "").strip()
        treatment_code = str(row["treatment_code"] or "").strip()
        if clutch_code and treatment_code:
            pairs.append((clutch_code, treatment_code))

    # de-duplicate
    seen = set()
    uniq: List[Tuple[str, str]] = []
    for cc, tc in pairs:
        key = (cc, tc)
        if key not in seen:
            seen.add(key)
            uniq.append(key)

    return uniq


def main() -> None:
    if not DB_URL:
        raise RuntimeError("DB_URL is not set in the environment")

    mapping_csv = "seed_kits/legacy_wrangling_v2/working/clutch_treatment_mapping_v11.csv"
    print(f"[INFO] Loading mapping from: {mapping_csv}")

    pairs = load_mapping(mapping_csv)
    print(f"[INFO] {len(pairs)} unique clutch_code/treatment_code pair(s) in mapping")

    if not pairs:
        print("[WARN] No pairs in mapping; nothing to load.")
        return

    engine = create_engine(DB_URL)

    clutch_codes = sorted({c for c, _ in pairs})
    treat_codes = sorted({t for _, t in pairs})

    with engine.begin() as cx:
        # clutch_code -> clutch_id
        clutch_df = pd.read_sql(
            text("""
              SELECT clutch_code, id::text AS clutch_id
              FROM public.clutches
              WHERE clutch_code = ANY(:codes)
            """),
            cx,
            params={"codes": clutch_codes},
        )
        clutch_map: Dict[str, str] = dict(zip(clutch_df["clutch_code"], clutch_df["clutch_id"]))

        # treatment_code -> treatment_id
        treat_df = pd.read_sql(
            text("""
              SELECT treat_code, id::text AS treatment_id
              FROM public.treatments
              WHERE treat_code = ANY(:codes)
            """),
            cx,
            params={"codes": treat_codes},
        )
        treat_map: Dict[str, str] = dict(zip(treat_df["treat_code"], treat_df["treatment_id"]))

        inserted = 0
        skipped_existing = 0
        missing_clutch = 0
        missing_treat = 0

        for clutch_code, treat_code in pairs:
            cid = clutch_map.get(clutch_code)
            if not cid:
                missing_clutch += 1
                print(f"[WARN] clutch_code '{clutch_code}' not found in public.clutches; skipping")
                continue

            tid = treat_map.get(treat_code)
            if not tid:
                missing_treat += 1
                print(f"[WARN] treat_code '{treat_code}' not found in public.treatments; skipping")
                continue

            # check if link already exists
            exists_df = pd.read_sql(
                text("""
                  SELECT 1
                  FROM public.join_clutch_treatments
                  WHERE clutch_id = CAST(:cid AS uuid)
                    AND treatment_id = CAST(:tid AS uuid)
                  LIMIT 1
                """),
                cx,
                params={"cid": cid, "tid": tid},
            )
            if not exists_df.empty:
                skipped_existing += 1
                continue

            cx.execute(
                text("""
                  INSERT INTO public.join_clutch_treatments
                    (id, clutch_id, treatment_id, applied_at, created_at, notes)
                  VALUES
                    (gen_random_uuid(),
                     CAST(:cid AS uuid),
                     CAST(:tid AS uuid),
                     now(),
                     now(),
                     'legacy_v9/v10_mapping_csv')
                """),
                {"cid": cid, "tid": tid},
            )
            inserted += 1

    print(f"[OK] Inserted {inserted} join_clutch_treatments row(s).")
    print(f"[INFO] Existing links skipped: {skipped_existing}")
    print(f"[INFO] Missing clutch_code:   {missing_clutch}")
    print(f"[INFO] Missing treat_code:    {missing_treat}")
