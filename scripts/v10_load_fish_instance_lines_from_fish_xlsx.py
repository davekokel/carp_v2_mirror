from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Optional

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


BAD_BASES = {"", "wt", "wildtype", "nan", "none"}


def norm(s: str | None) -> str:
    if s is None:
        return ""
    return str(s).strip().lower()


def is_real_basecode(s: str | None) -> bool:
    if s is None:
        return False
    v = str(s).strip()
    if not v:
        return False
    return v.lower() not in BAD_BASES


def get_engine(db_url: Optional[str]) -> Engine:
    url = db_url or os.environ.get("DB_URL")
    if not url:
        raise SystemExit("DB_URL must be provided via --db-url or env DB_URL")
    print(f"DB_URL={url}")
    return create_engine(url)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="v10: load fish_instance lines from fish.xlsx into fish_instance + join_fish_transgene_alleles"
    )
    parser.add_argument(
        "--fish-xlsx",
        required=True,
        help="Path to fish.xlsx (e.g. seed_kits/2025-11-15-121231-autoload/fish.xlsx)",
    )
    parser.add_argument(
        "--db-url",
        help="Override DB_URL",
    )
    args = parser.parse_args()

    path = Path(args.fish_xlsx)
    if not path.exists():
        raise SystemExit(f"fish.xlsx not found: {path}")

    df = pd.read_excel(path)
    print(f"[v10_load_fish_instance_lines] read {len(df)} row(s) from {path}")

    required_cols = [
        "nickname",
        "birthday",
        "genetic_background",
        "line_building_stage",
        "transgene_base_code",
        "allele_nickname",
        "zygosity",
    ]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise SystemExit(f"fish.xlsx missing required columns: {missing}; found {list(df.columns)}")

    df = df.copy()
    df["base_code"] = df["transgene_base_code"].astype(str).str.strip()
    df["allele_nickname"] = df["allele_nickname"].astype(str)

    df["nick_key"]  = df["nickname"].map(norm)
    df["bg_key"]    = df["genetic_background"].map(norm)
    df["stage_key"] = df["line_building_stage"].map(norm)

    print("[v10_load_fish_instance_lines] stage_key value_counts:")
    print(df["stage_key"].value_counts(dropna=False).to_string())

    # Step 1: candidate line-def rows
    df_lines = df[
        df["base_code"].map(is_real_basecode)
        & df["stage_key"].isin(["p0", "stable", "f1", "f2"])
    ].copy()

    print(f"[v10_load_fish_instance_lines] candidate line-def rows after filter: {len(df_lines)}")
    if df_lines.empty:
        print("[v10_load_fish_instance_lines] no candidate line-definition rows; exiting.")
        return

    # Collapse to unique lines
    df_lines = df_lines[[
        "nick_key",
        "bg_key",
        "stage_key",
        "base_code",
        "allele_nickname",
        "nickname",
        "genetic_background",
        "line_building_stage",
        "birthday",
        "zygosity",
    ]].drop_duplicates()

    print(f"[v10_load_fish_instance_lines] prepared {len(df_lines)} unique line rows")

    engine = get_engine(args.db_url)

    # Step 2: restrict to known constructs (base_code ∈ transgenes)
    with engine.begin() as cx:
        df_known = pd.read_sql(
            text("SELECT transgene_base_code FROM public.transgenes"),
            cx,
        )
    known_bases = set(df_known["transgene_base_code"].astype(str).str.strip())

    mask_known = df_lines["base_code"].isin(known_bases)
    n_unknown = int((~mask_known).sum())
    if n_unknown > 0:
        skipped = df_lines.loc[~mask_known, "base_code"].dropna().astype(str).unique().tolist()
        print(
            f"[v10_load_fish_instance_lines] SKIP: {n_unknown} line row(s) with base_code not in constructs: {skipped}"
        )

    df_lines = df_lines.loc[mask_known].copy()

    if df_lines.empty:
        print("[v10_load_fish_instance_lines] after filtering by known constructs, no lines remain; exiting.")
        return

    print(f"[v10_load_fish_instance_lines] lines after known-construct filter: {len(df_lines)}")

    sql_insert_fish = text(
        """
        INSERT INTO public.fish_instance (
          fish_code,
          fish_group_id,
          birthday,
          nickname,
          genetic_background,
          line_building_stage,
          notes,
          created_at
        )
        VALUES (
          'FSH-' || LEFT(uuid_generate_v4()::text, 8),
          NULL,
          :birthday,
          :nickname,
          :bg,
          :stage,
          :notes,
          now()
        )
        RETURNING id::text AS fish_id
        """
    )

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

    insert_jfta = text(
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

    inserted_fish = 0
    inserted_jfta = 0
    skipped_alloc = 0

    with engine.begin() as cx:
        for _, row in df_lines.iterrows():
            nickname = str(row["nickname"]).strip()
            bg       = str(row["genetic_background"]).strip()
            stage    = str(row["line_building_stage"]).strip()
            birthday = row["birthday"]
            zygosity = None if pd.isna(row["zygosity"]) else str(row["zygosity"]).strip()
            base_code    = row["base_code"]
            allele_nick  = str(row["allele_nickname"]).strip()

            res2 = cx.execute(
                sql_insert_fish,
                {
                    "birthday": birthday,
                    "nickname": nickname,
                    "bg": bg,
                    "stage": stage,
                    "notes": None,
                },
            ).fetchone()
            fish_id = res2._mapping["fish_id"]
            inserted_fish += 1

            res3 = cx.execute(
                ensure_sql,
                {"base_code": base_code, "allele_nickname": allele_nick},
            ).fetchone()

            if res3 is None:
                print(f"[v10_load_fish_instance_lines] WARN: allocator returned no row for base_code={base_code}, nick={allele_nick}")
                skipped_alloc += 1
                continue

            allele_number = int(res3._mapping["allele_number"])

            cx.execute(
                insert_jfta,
                {
                    "fish_id": fish_id,
                    "base_code": base_code,
                    "allele_number": allele_number,
                    "zygosity": zygosity,
                },
            )
            inserted_jfta += 1

    print(f"[v10_load_fish_instance_lines] inserted {inserted_fish} new fish_instance line row(s)")
    print(f"[v10_load_fish_instance_lines] linked {inserted_jfta} allele row(s)")
    print(f"[v10_load_fish_instance_lines] skipped {skipped_alloc} allocator call(s)")


if __name__ == "__main__":
    main()
