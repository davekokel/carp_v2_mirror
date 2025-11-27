from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Optional, Dict

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from uuid import uuid4

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
    url = db_url or os.getenv("DB_URL")
    if not url:
        raise SystemExit("DB_URL must be provided via --db-url or env DB_URL")
    print(f"DB_URL={url}")
    return create_engine(url)


def main() -> None:
    print("[v10_seed_fish_lines] START")
    parser = argparse.ArgumentParser(
        description="v10: seed fish_instances_v10 from fish.xlsx and existing fish_lines."
    )
    parser.add_argument(
        "--fish-xlsx",
        required=True,
        help="Path to fish.xlsx used to build fish_lines.",
    )
    parser.add_argument(
        "--db-url",
        help="Override DB_URL",
    )
    args = parser.parse_args()

    path = Path(args.fish_xlsx)
    if not path.exists():
        print(f"[v10_seed_fish_lines] fish.xlsx not found: {path}")
        return

    df = pd.read_excel(path)
    print(f"[v10_seed_fish_lines] read {len(df)} row(s) from {path}")

    required = [
        "nickname",
        "birthday",
        "genetic_background",
        "line_building_stage",
        "transgene_base_code",
        "allele_nickname",
    ]
    missing = [c for c in required if c not in df.columns]
    if missing:
        print(f"[v10_seed_fish_lines] missing columns: {missing}; exiting.")
        return

    df = df.copy()
    df["birthday"] = pd.to_datetime(df["birthday"], errors="coerce").dt.date
    df["transgene_base_code"] = df["transgene_base_code"].astype(str)
    df["allele_nickname"] = df["allele_nickname"].astype(str)

    df["bg_key"] = df["genetic_background"].apply(norm)
    df["stage_key"] = df["line_building_stage"].apply(norm)
    df["nick_norm"] = df["nickname"].apply(norm)
    df["allele_nick_norm"] = df["allele_nickname"].apply(norm)
    df["base_norm"] = df["transgene_base_code"].apply(norm)

    # stages that represent real lines
    stage_ok = {"p0", "f1", "f2", "founder", "stable"}
    df = df[df["stage_key"].isin(stage_ok)].copy()

    df["base_ok"] = df["transgene_base_code"].apply(is_real_basecode)
    df = df[df["base_ok"]].copy()

    df = df.drop_duplicates(
        subset=[
            "nickname",
            "birthday",
            "genetic_background",
            "line_building_stage",
            "transgene_base_code",
            "allele_nickname",
        ]
    ).reset_index(drop=True)

    print(f"[v10_seed_fish_lines] candidate seed rows: {len(df)}")
    if df.empty:
        print("[v10_seed_fish_lines] no candidate seed rows; exiting.")
        return

    engine = get_engine(args.db_url)

    # ───────────────── map from fish_lines only (no genotype re-matching) ─────────────────
    with engine.begin() as cx:
        map_sql = text(
            """
            SELECT
              fl.id::text AS line_id,
              fl.line_code,
              lower(trim(fl.genetic_background)) AS bg_key,
              lower(trim(fl.nickname)) AS nick_norm,
              lower(fl.line_building_stage) AS stage_key
            FROM public.fish_lines fl
            """
        )
        df_map = pd.read_sql(map_sql, cx)

    df_map["bg_key"] = df_map["bg_key"].apply(norm)
    df_map["stage_key"] = df_map["stage_key"].apply(norm)
    df_map["nick_norm"] = df_map["nick_norm"].apply(norm)

    # join ONLY on nickname + background + stage
    merged = df.merge(
        df_map,
        how="left",
        left_on=["nick_norm", "bg_key", "stage_key"],
        right_on=["nick_norm", "bg_key", "stage_key"],
        suffixes=("_seed", "_line"),
    )

    missing = merged["line_id"].isna().sum()
    if missing:
        print(
            f"[v10_seed_fish_lines] WARN: {missing} seed row(s) had no matching fish_line; they will be skipped"
        )
        merged = merged[~merged["line_id"].isna()].copy()

    if merged.empty:
        print("[v10_seed_fish_lines] no seed rows matched existing fish_lines; exiting.")
        return

    merged["birthday"] = merged["birthday"].astype("datetime64[ns]").dt.date

    # one instance per (line_id, stage, birthday, base_code, allele_nickname)
    merged.sort_values(
        ["line_id", "stage_key", "birthday", "base_norm", "allele_nick_norm", "nickname"],
        inplace=True,
    )

    merged = merged.drop_duplicates(
        subset=["line_id", "stage_key", "birthday", "base_norm", "allele_nick_norm"]
    ).reset_index(drop=True)

    insert_sql = text(
        """
        INSERT INTO public.fish_instances_v10 (
          id,
          line_id,
          line_instance_code,
          fish_code,
          created_at,
          birthday
        )
        VALUES (
          gen_random_uuid(),
          :line_id,
          :line_instance_code,
          :fish_code,
          now(),
          :birthday
        )
        ON CONFLICT DO NOTHING
        """
    )

    inserted = 0
    with engine.begin() as cx:
        counts: Dict[str, int] = {}
        for _, row in merged.iterrows():
            line_id = row["line_id"]
            line_code = row["line_code"]
            birthday = row["birthday"]

            if not line_id or pd.isna(birthday):
                continue

            counts[line_id] = counts.get(line_id, 0) + 1
            idx = counts[line_id]

            line_instance_code = f"{line_code}-{idx:03d}"
            fish_code = f"FSH-{uuid4().hex[:8]}"

            cx.execute(
                insert_sql,
                {
                    "line_id": line_id,
                    "line_instance_code": line_instance_code,
                    "fish_code": fish_code,
                    "birthday": birthday,
                },
            )
            inserted += 1

    print(f"[v10_seed_fish_lines] inserted {inserted} fish_instances_v10")


if __name__ == "__main__":
    main()