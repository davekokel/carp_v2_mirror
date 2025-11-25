from __future__ import annotations

import argparse
import os
from typing import Optional

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


def get_engine(db_url: Optional[str]) -> Engine:
    url = db_url or os.environ.get("DB_URL")
    if not url:
        raise SystemExit("DB_URL must be provided via --db-url or DB_URL env")
    print(f"DB_URL={url}")
    return create_engine(url)


def pick_column(df: pd.DataFrame, candidates: list[str], label: str) -> str:
    for c in candidates:
        if c in df.columns:
            return c
    raise SystemExit(
        f"v9_load_rnas_from_constructs: could not find {label} column; "
        f"tried {candidates}, got columns={list(df.columns)}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="v9: load RNAs into public.rnas from constructs CSV (e.g. constructs_plasmid.csv)",
    )
    parser.add_argument(
        "--constructs-csv",
        required=True,
        help="Path to constructs CSV (e.g. seed_kits/.../constructs_plasmid.csv)",
    )
    parser.add_argument(
        "--db-url",
        help="Postgres DB URL (overrides DB_URL env)",
    )
    args = parser.parse_args()

    path = args.constructs_csv
    df = pd.read_csv(path)
    print(f"v9_load_rnas_from_constructs: read {len(df)} row(s) from {path}")

    # auto-detect columns
    rna_flag_col = pick_column(
        df,
        ["used_for_injection_rna", "rna", "is_rna", "rna_flag"],
        "RNA flag",
    )
    code_col = pick_column(
        df,
        ["rna_base_code", "plasmid_code", "code"],
        "RNA base code",
    )
    name_col = "plasmid_name" if "plasmid_name" in df.columns else ("name" if "name" in df.columns else None)

    # filter to rows where RNA flag is truthy (1 / True / '1' / 'true')
    flag = df[rna_flag_col]
    flag_num = pd.to_numeric(flag, errors="coerce").fillna(0).astype(int)
    df_rna = df[flag_num == 1].copy()

    if df_rna.empty:
        print("v9_load_rnas_from_constructs: no rows with RNA flag == 1; nothing to do.")
        return

    # dedupe by RNA base code
    df_rna["rna_base_code"] = df_rna[code_col].astype(str).str.strip()
    if name_col:
        df_rna["rna_name"] = df_rna[name_col].astype(str).str.strip()
    else:
        df_rna["rna_name"] = df_rna["rna_base_code"]

    df_rna = df_rna[["rna_base_code", "rna_name"]].drop_duplicates(subset=["rna_base_code"])
    print(f"v9_load_rnas_from_constructs: prepared {len(df_rna)} unique RNA code(s)")

    engine = get_engine(args.db_url)

    sql = text(
        """
        INSERT INTO public.rnas (rna_base_code, name, notes)
        VALUES (:code, :name, NULL)
        ON CONFLICT (rna_base_code) DO UPDATE
          SET name = EXCLUDED.name
        """
    )

    inserted = 0
    with engine.begin() as cx:
        for _, row in df_rna.iterrows():
            code = row["rna_base_code"]
            name = row["rna_name"]
            if not code:
                continue
            cx.execute(sql, {"code": code, "name": name})
            inserted += 1

    print(f"v9_load_rnas_from_constructs: upserted {inserted} row(s) into public.rnas")


if __name__ == "__main__":
    main()
