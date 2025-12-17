from __future__ import annotations

import os
import argparse
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mapping-csv",
        required=True,
        help="Path to clutch_treatment_mapping_v11.csv (REQUIRED; do not rely on v2 defaults)",
    )

    parser.add_argument(
        "--db-url",
        default=os.getenv("DB_URL"),
        help="Database URL (defaults to DB_URL env var)",
    )
    args = parser.parse_args()

    if not args.db_url:
        raise SystemExit("DB_URL is not set and --db-url not provided.")

    path = Path(args.mapping_csv)
    if not path.exists():
        raise SystemExit(f"Mapping CSV not found: {path}")

    df = pd.read_csv(path)

    # Accept either 'treat_code' or 'treatment_code'
    col = None
    if "treat_code" in df.columns:
        col = "treat_code"
    elif "treatment_code" in df.columns:
        col = "treatment_code"
    else:
        raise SystemExit(
            "mapping CSV must have a 'treat_code' or 'treatment_code' column."
        )

    codes = sorted(
        {c for c in df[col].dropna().astype(str) if c and c.lower() != "nan"}
    )
    if not codes:
        print(
            "[WARN] No treat_code/treatment_code values found in mapping CSV; nothing to validate."
        )
        return

    eng = create_engine(args.db_url)

    with eng.begin() as cx:
        existing = {
            row[0]
            for row in cx.execute(
                text(
                    """
                    SELECT treat_code
                    FROM public.treatments
                    WHERE treat_code = ANY(:codes)
                    """
                ),
                {"codes": codes},
            )
        }

    missing = [code for code in codes if code not in existing]

    if not missing:
        print(
            f"[OK] legacy treatments validation: all {len(codes)} treat_code(s) present in public.treatments."
        )
        return

    # v11 behaviour: warn but do not abort.
    n_missing = len(missing)
    n_total = len(codes)
    print(
        f"[WARN] legacy treatments validation: {n_total - n_missing} of {n_total} treat_code(s) "
        f"present in public.treatments; {n_missing} missing."
    )
    print(
        "[WARN] mapping CSV references treat_code(s) not present in public.treatments: "
        + ", ".join(sorted(missing))
    )
    print(
        "[WARN] Proceeding anyway; subsequent mapping/apply steps will skip missing treatments."
    )


if __name__ == "__main__":
    main()
