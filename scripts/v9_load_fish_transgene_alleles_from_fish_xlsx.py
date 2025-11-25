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


def norm(s) -> str:
    if s is None:
        return ""
    return str(s).strip().lower()


BAD_BASES = {"", "wt", "wildtype", "nan", "none"}


def is_real_basecode(s: str | None) -> bool:
    if s is None:
        return False
    val = str(s).strip()
    if not val:
        return False
    if val.lower() in BAD_BASES:
        return False
    return True


def main() -> None:
    parser = argparse.ArgumentParser(
        description="v9: load join_fish_transgene_alleles from fish.xlsx (nickname+background → basecodes via allocator)."
    )
    parser.add_argument(
        "--fish-xlsx",
        required=True,
        help="Path to fish.xlsx (e.g. seed_kits/2025-11-15-121231-autoload/fish.xlsx)",
    )
    parser.add_argument(
        "--db-url",
        help="Postgres DB URL (overrides DB_URL env)",
    )
    args = parser.parse_args()

    # --- read fish.xlsx ---
    fx_path = args.fish_xlsx
    if not os.path.exists(fx_path):
        raise SystemExit(f"fish.xlsx not found: {fx_path}")

    df_fx = pd.read_excel(fx_path)
    print(f"[v9_load_fish_transgene_alleles_from_fish_xlsx] read {len(df_fx)} row(s) from {fx_path}")

    required_cols = [
        "nickname",
        "birthday",
        "genetic_background",
        "line_building_stage",
        "transgene_base_code",
        "allele_nickname",
        "zygosity",
    ]
    missing = [c for c in required_cols if c not in df_fx.columns]
    if missing:
        raise SystemExit(
            f"fish.xlsx missing required columns: {missing}. "
            f"Found: {list(df_fx.columns)}"
        )

    df_fx = df_fx.copy()
    df_fx["transgene_base_code"] = df_fx["transgene_base_code"].astype(str)

    # keep only rows with a real transgene basecode (not WT, not blank, not nan)
    df_fx = df_fx[df_fx["transgene_base_code"].map(is_real_basecode)]

    if df_fx.empty:
        print("[v9] no rows with real transgene_base_code; nothing to do.")
        return

    # normalize keys to match fish_instance
    df_fx["nick_key"] = df_fx["nickname"].map(norm)
    df_fx["bg_key"]   = df_fx["genetic_background"].map(norm)

    # allele_nickname stays STRING always (even if looks numeric)
    df_fx["allele_nickname"] = df_fx["allele_nickname"].astype(str)

    # collapse per line: (nickname, background, basecode, allele_nickname, zygosity)
    df_fx = df_fx[[
        "nick_key",
        "bg_key",
        "transgene_base_code",
        "allele_nickname",
        "zygosity",
    ]].drop_duplicates()

    print(f"[v9] prepared {len(df_fx)} unique (nickname, bg, basecode, allele_nickname) line rows")

    # --- connect to DB and read fish_instance ---
    engine = get_engine(args.db_url)

    sql_fish = text(
        """
        SELECT
          id::text      AS fish_id,
          fish_code,
          nickname,
          genetic_background,
          line_building_stage
        FROM public.fish_instance
        """
    )
    with engine.begin() as cx:
        df_fi = pd.read_sql(sql_fish, cx)

    if df_fi.empty:
        print("[v9] no rows in public.fish_instance; nothing to do.")
        return

    df_fi = df_fi.copy()
    df_fi["nick_key"] = df_fi["nickname"].map(norm)
    df_fi["bg_key"]   = df_fi["genetic_background"].map(norm)

    # join fish_instances to line definitions by (nickname, background) only
    df_join = df_fi[["fish_id", "fish_code", "nick_key", "bg_key"]].merge(
        df_fx,
        on=["nick_key", "bg_key"],
        how="inner",
        suffixes=("_fi", "_fx"),
    )

    if df_join.empty:
        print("[v9] no fish_instance rows matched fish.xlsx by (nickname, background).")
        return

    print(
        f"[v9] matched {len(df_join)} fish_instance×line rows "
        f"({df_join['fish_id'].nunique()} distinct fish)"
    )

    # prepare rows: one per fish / basecode / allele_nickname / zygosity
    df_jfta = df_join[[
        "fish_id",
        "fish_code",
        "transgene_base_code",
        "allele_nickname",
        "zygosity",
    ]].drop_duplicates()

    ensure_sql = text(
        """
        SELECT
          transgene_base_code,
          allele_number,
          allele_name,
          allele_nickname
        FROM public.ensure_transgene_allele(:base_code, :allele_nickname)
        """
    )

    insert_sql = text(
        """
        INSERT INTO public.join_fish_transgene_alleles (
          fish_id,
          transgene_base_code,
          allele_number,
          zygosity,
          created_at
        )
        VALUES (
          :fish_id,
          :base_code,
          :allele_number,
          :zygosity,
          now()
        )
        ON CONFLICT (fish_id, transgene_base_code, allele_number) DO NOTHING
        """
    )

    inserted = 0
    skipped_unknown = 0

    with engine.begin() as cx:
        for _, row in df_jfta.iterrows():
            base_code = str(row["transgene_base_code"]).strip()
            nick      = str(row["allele_nickname"]).strip()
            zygosity  = None if pd.isna(row["zygosity"]) else str(row["zygosity"]).strip()

            res = cx.execute(
                ensure_sql,
                {"base_code": base_code, "allele_nickname": nick},
            ).fetchone()

            if res is None:
                print(f"[v9] WARN: ensure_transgene_allele returned no row for base_code={base_code}, nickname={nick}")
                skipped_unknown += 1
                continue

            allele_number = res["allele_number"]

            cx.execute(
                insert_sql,
                {
                    "fish_id": row["fish_id"],
                    "base_code": base_code,
                    "allele_number": int(allele_number),
                    "zygosity": zygosity,
                },
            )
            inserted += 1

    print(f"[v9] upserted {inserted} row(s) into public.join_fish_transgene_alleles")
    if skipped_unknown:
        print(f"[v9] skipped {skipped_unknown} row(s) due to unknown basecodes or allocator returns")
