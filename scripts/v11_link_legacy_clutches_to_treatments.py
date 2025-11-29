from __future__ import annotations

import argparse
import os
from typing import List, Tuple, Dict

import pandas as pd
from sqlalchemy import create_engine, text

DB_URL = os.getenv("DB_URL")


def load_mapping(csv_path: str) -> List[Tuple[str, str]]:
    """
    Load a clutch→treat mapping from CSV.

    Supported columns:
      - clutch_code, treat_code
      - clutch_code, treat_codes (codes separated by '+' or ';')

    Returns list of (clutch_code, treat_code) pairs.
    """
    df = pd.read_csv(csv_path)

    if "clutch_code" not in df.columns:
        raise ValueError("CSV must have a 'clutch_code' column")

    pairs: List[Tuple[str, str]] = []

    if "treat_code" in df.columns:
        for _, row in df.iterrows():
            clutch = str(row["clutch_code"]).strip()
            code = str(row["treat_code"]).strip()
            if clutch and code:
                pairs.append((clutch, code))

    elif "treat_codes" in df.columns:
        for _, row in df.iterrows():
            clutch = str(row["clutch_code"]).strip()
            raw = str(row["treat_codes"] or "").strip()
            if not clutch or not raw:
                continue
            # split by '+' or ';'
            tokens = []
            for part in raw.replace(";", "+").split("+"):
                code = part.strip()
                if code:
                    tokens.append(code)
            for code in tokens:
                pairs.append((clutch, code))
    else:
        raise ValueError("CSV must have either 'treat_code' or 'treat_codes' column")

    # de-duplicate pairs
    seen: Dict[Tuple[str, str], None] = {}
    out: List[Tuple[str, str]] = []
    for clutch, code in pairs:
        key = (clutch, code)
        if key not in seen:
            seen[key] = None
            out.append(key)

    return out


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Link legacy clutches to treatments via join_clutch_treatments"
    )
    parser.add_argument(
        "--csv",
        required=True,
        help="CSV file with clutch_code + treat_code(s)",
    )
    args = parser.parse_args()

    if not DB_URL:
        raise RuntimeError("DB_URL is not set in the environment")

    engine = create_engine(DB_URL)

    # Load mapping from CSV
    pairs = load_mapping(args.csv)
    if not pairs:
        print("[WARN] No clutch/treatment pairs parsed from CSV.")
        return

    clutch_codes = sorted({c for c, _ in pairs})
    treat_codes = sorted({t for _, t in pairs})

    print(f"[INFO] Parsed {len(pairs)} clutch/treat pairs")
    print(f"[INFO] Unique clutches:  {len(clutch_codes)}")
    print(f"[INFO] Unique treatcodes: {len(treat_codes)}")

    with engine.begin() as cx:
        # Map clutch_code → clutch_id
        clutch_df = pd.read_sql(
            text("""
              SELECT clutch_code, id::text AS clutch_id
              FROM public.clutches
              WHERE clutch_code = ANY(:codes)
            """),
            cx,
            params={"codes": clutch_codes},
        )
        clutch_map = dict(zip(clutch_df["clutch_code"], clutch_df["clutch_id"]))

        # Map treat_code → treatment_id
        treat_df = pd.read_sql(
            text("""
              SELECT treat_code, id::text AS treatment_id
              FROM public.treatments
              WHERE treat_code = ANY(:codes)
            """),
            cx,
            params={"codes": treat_codes},
        )
        treat_map = dict(zip(treat_df["treat_code"], treat_df["treatment_id"]))

        missing_clutches = 0
        missing_treats = 0
        inserted = 0
        skipped_existing = 0

        for clutch_code, treat_code in pairs:
            clutch_id = clutch_map.get(clutch_code)
            if not clutch_id:
                missing_clutches += 1
                print(f"[WARN] clutch_code '{clutch_code}' not found; skipping")
                continue
            treatment_id = treat_map.get(treat_code)
            if not treatment_id:
                missing_treats += 1
                print(f"[WARN] treat_code '{treat_code}' not found; skipping")
                continue

            # Check if link already exists
            exists_df = pd.read_sql(
                text("""
                  SELECT 1
                  FROM public.join_clutch_treatments
                  WHERE clutch_id = CAST(:cid AS uuid)
                    AND treatment_id = CAST(:tid AS uuid)
                  LIMIT 1
                """),
                cx,
                params={"cid": clutch_id, "tid": treatment_id},
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
                     'legacy_v10_link')
                """),
                {"cid": clutch_id, "tid": treatment_id},
            )
            inserted += 1

    print(f"[OK] Inserted {inserted} join_clutch_treatments row(s).")
    print(f"[INFO] Existing links skipped: {skipped_existing}")
    print(f"[INFO] Missing clutches:      {missing_clutches}")
    print(f"[INFO] Missing treatcodes:    {missing_treats}")


if __name__ == "__main__":
    main()