import os
import argparse

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


def get_engine() -> Engine:
    db_url = os.environ.get("DB_URL")
    if not db_url:
        raise RuntimeError("DB_URL environment variable is not set")
    print(f"DB_URL={db_url}")
    return create_engine(db_url)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Load fluor aliases into fluor_aliases from alias.csv"
    )
    parser.add_argument(
        "--alias-csv",
        required=True,
        help="Path to alias.csv",
    )
    args = parser.parse_args()

    if not os.path.exists(args.alias_csv):
        raise FileNotFoundError(f"alias CSV not found: {args.alias_csv}")

    df = pd.read_csv(args.alias_csv)

    required_cols = {"target_kind", "target_key", "alias"}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"alias.csv is missing required columns: {missing}")

    # only keep fluor rows
    df = df[df["target_kind"] == "fluor"].copy()
    if df.empty:
        print("No fluor rows in alias.csv; nothing to do.")
        return

    engine = get_engine()

    # v11: CASE-INSENSITIVE match against nickname / display_name
    lookup_sql = text(
        """
        SELECT id
        FROM public.fluors
        WHERE lower(nickname) = lower(:label)
           OR lower(display_name) = lower(:label)
        """
    )
    upsert_sql = text(
        """
        INSERT INTO public.fluor_aliases (fluor_id, alias)
        VALUES (:fluor_id, :alias)
        ON CONFLICT (alias) DO UPDATE
        SET fluor_id = EXCLUDED.fluor_id
        """
    )

    handled = 0
    skipped = 0

    with engine.begin() as cx:
        for _, row in df.iterrows():
            target_key = str(row["target_key"]).strip()
            alias = str(row["alias"]).strip()

            if not target_key or not alias:
                continue

            fluor_id = cx.execute(
                lookup_sql, {"label": target_key}
            ).scalar()
            if fluor_id is None:
                print(
                    f"[WARN] alias '{alias}': target_key '{target_key}' "
                    "not found in public.fluors; skipping"
                )
                skipped += 1
                continue

            cx.execute(upsert_sql, {"fluor_id": fluor_id, "alias": alias})
            handled += 1

    print(f"fluor_aliases: handled={handled}, skipped={skipped}")


if __name__ == "__main__":
    main()
