from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Optional, Dict, Tuple

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


def build_construct_lookup(engine: Engine) -> Dict[str, Tuple[str, str]]:
    """
    key -> (construct_id, canonical_code)

    Keys include:
      - constructs.construct_code
      - constructs.base_code
      - construct_aliases.alias

    Both raw and lowercased forms are accepted.
    """
    sql = text(
        """
        SELECT
          c.id::text      AS construct_id,
          c.construct_code,
          c.base_code,
          a.alias
        FROM public.constructs c
        LEFT JOIN public.construct_aliases a
          ON a.construct_id = c.id
        """
    )
    with engine.begin() as cx:
        df = pd.read_sql(sql, cx)

    lookup: Dict[str, Tuple[str, str]] = {}
    for _, row in df.iterrows():
        construct_id = str(row["construct_id"]).strip()
        construct_code = (row["construct_code"] or "").strip() if row["construct_code"] is not None else ""
        base_code = (row["base_code"] or "").strip() if row["base_code"] is not None else ""
        alias = (row["alias"] or "").strip() if row.get("alias") is not None else ""

        canon = construct_code or base_code

        keys = set()
        if construct_code:
            keys.add(construct_code)
        if base_code:
            keys.add(base_code)
        if alias:
            keys.add(alias)

        for k in keys:
            if not k:
                continue
            lookup[k] = (construct_id, canon or k)
            lookup[k.lower()] = (construct_id, canon or k.lower())

    print(f"[v10_load_fish_lines] construct lookup keys: {len(lookup)}")
    return lookup


def main() -> None:
    print("[v10_load_fish_lines] START")
    parser = argparse.ArgumentParser(
        description="v10: load fish_lines + join_line_alleles from fish.xlsx (alias-aware)."
    )
    parser.add_argument(
        "--fish-xlsx",
        required=True,
        help="Path to fish.xlsx",
    )
    parser.add_argument(
        "--db-url",
        help="Override DB_URL",
    )
    args = parser.parse_args()

    path = Path(args.fish_xlsx)
    if not path.exists():
        print(f"[v10_load_fish_lines] fish.xlsx not found: {path}")
        return

    df = pd.read_excel(path)
    print(f"[v10_load_fish_lines] read {len(df)} row(s) from {path}")

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
        print(f"[v10_load_fish_lines] missing columns: {missing}; exiting.")
        return

    df = df.copy()
    df["base_code_raw"] = df["transgene_base_code"].astype(str).str.strip()
    df["allele_nickname"] = df["allele_nickname"].astype(str)

    df["nick_key"]  = df["nickname"].map(norm)
    df["bg_key"]    = df["genetic_background"].map(norm)
    df["stage_key"] = df["line_building_stage"].map(norm)

    print("[v10_load_fish_lines] stage_key value_counts:")
    print(df["stage_key"].value_counts(dropna=False).to_string())

    # keep only real basecodes and line-building stages we care about
    mask_stage = df["stage_key"].isin(["p0", "stable", "f1", "f2", "founder"])
    mask_base  = df["base_code_raw"].map(is_real_basecode)
    df = df[mask_stage & mask_base].copy()

    print(f"[v10_load_fish_lines] candidate rows after filters: {len(df)}")
    if df.empty:
        print("[v10_load_fish_lines] no candidate rows after stage/base filters; exiting.")
        return

    engine = get_engine(args.db_url)

    # alias-aware construct lookup
    construct_lookup = build_construct_lookup(engine)

    def resolve_construct(code: str) -> Tuple[Optional[str], Optional[str]]:
        c = code.strip()
        if not c:
            return None, None
        if c in construct_lookup:
            return construct_lookup[c]
        cl = c.lower()
        if cl in construct_lookup:
            return construct_lookup[cl]
        return None, None

    # resolve construct_id + canonical code
    df["construct_id"] = None
    df["construct_code_canon"] = None

    missing_construct = 0
    missing_codes: set[str] = set()

    for idx, code in df["base_code_raw"].items():
        cid, canon = resolve_construct(str(code))
        if cid is None:
            missing_construct += 1
            missing_codes.add(str(code))
        else:
            df.at[idx, "construct_id"] = cid
            df.at[idx, "construct_code_canon"] = canon

    if missing_construct:
        print(
            f"[v10_load_fish_lines] SKIP: {missing_construct} row(s) with base_code not resolvable via constructs/aliases: "
            f"{sorted(missing_codes)}"
        )
        df = df[df["construct_id"].notna()].copy()

    if df.empty:
        print("[v10_load_fish_lines] after construct resolution, no rows remain; exiting.")
        return

    # line_key = (nickname, background, stage)
    df["line_key"] = df["nick_key"] + "|" + df["bg_key"] + "|" + df["stage_key"]
    n_line_keys = df["line_key"].nunique()
    print(f"[v10_load_fish_lines] prepared {len(df)} cleaned rows, {n_line_keys} unique line_keys")

    insert_line_sql = text(
        """
        INSERT INTO public.fish_lines (
          line_code,
          nickname,
          genetic_background,
          line_building_stage,
          notes,
          created_at
        )
        VALUES (
          :line_code,
          :nickname,
          :bg,
          :stage,
          :notes,
          now()
        )
        RETURNING id::text AS line_id
        """
    )

    ensure_sql = text(
        """
        SELECT
          transgene_base_code,
          allele_number,
          allele_name,
          allele_nickname
        FROM public.ensure_transgene_allele(:construct_code, :allele_nickname)
        """
    )

    insert_jla = text(
        """
        INSERT INTO public.join_line_alleles (
          line_id,
          construct_id,
          allele_number,
          zygosity,
          created_at
        )
        VALUES (
          :line_id,
          :construct_id,
          :allele_number,
          :zygosity,
          now()
        )
        ON CONFLICT (line_id, construct_id, allele_number) DO NOTHING
        """
    )

    inserted_lines = 0
    inserted_alleles = 0
    skipped_alloc = 0

    with engine.begin() as cx:
        for line_key, sub in df.groupby("line_key"):
            nickname = sub["nickname"].iloc[0]
            bg       = sub["genetic_background"].iloc[0]
            stage    = sub["line_building_stage"].iloc[0]

            line_code = f"LINE-{hash(line_key) & 0xffffffff:08x}"
            print(f"[v10_load_fish_lines] inserting line line_code={line_code} nickname={nickname}")

            res_line = cx.execute(
                insert_line_sql,
                {
                    "line_code": line_code,
                    "nickname": nickname,
                    "bg": bg,
                    "stage": stage,
                    "notes": None,
                },
            ).fetchone()
            line_id = res_line._mapping["line_id"]
            inserted_lines += 1

            for _, row in sub.iterrows():
                construct_id  = str(row["construct_id"]).strip()
                canon_code    = str(row["construct_code_canon"]).strip()
                allele_nick   = str(row["allele_nickname"]).strip()
                zygosity      = None if pd.isna(row["zygosity"]) else str(row["zygosity"]).strip()

                if not canon_code:
                    continue

                res3 = cx.execute(
                    ensure_sql,
                    {"construct_code": canon_code, "allele_nickname": allele_nick},
                ).fetchone()

                if res3 is None:
                    print(
                        f"[v10_load_fish_lines] WARN: allocator returned no row for construct_code={canon_code}, nick={allele_nick}"
                    )
                    skipped_alloc += 1
                    continue

                allele_number = int(res3._mapping["allele_number"])

                cx.execute(
                    insert_jla,
                    {
                        "line_id": line_id,
                        "construct_id": construct_id,
                        "allele_number": allele_number,
                        "zygosity": zygosity,
                    },
                )
                inserted_alleles += 1

    print(f"[v10_load_fish_lines] inserted {inserted_lines} fish_lines")
    print(f"[v10_load_fish_lines] linked {inserted_alleles} allele rows for lines")
    print(f"[v10_load_fish_lines] skipped {skipped_alloc} allocator call(s)")
if __name__ == "__main__":
    main()
