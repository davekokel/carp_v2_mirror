from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Optional, Dict, Tuple, Any, List

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
        description="v10: load fish_lines + join_line_alleles from fish.xlsx (genotype-defined lines)."
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

    df["nick_key"] = df["nickname"].map(norm)
    df["bg_key"] = df["genetic_background"].map(norm)
    df["stage_key"] = df["line_building_stage"].map(norm)

    print("[v10_load_fish_lines] stage_key value_counts:")
    print(df["stage_key"].value_counts(dropna=False).to_string())

    allowed_stages = {"p0", "stable", "f1", "f2", "founder"}
    mask_stage = df["stage_key"].isin(allowed_stages)
    df = df[mask_stage].copy()

    if df.empty:
        print("[v10_load_fish_lines] no rows after stage filter; exiting.")
        return

    df["has_real_base"] = df["base_code_raw"].map(is_real_basecode)
    df["bg_nonempty"] = df["genetic_background"].astype(str).str.strip() != ""

    background_only_mask = df["bg_nonempty"] & (~df["has_real_base"])
    transgenic_mask = df["has_real_base"]

    df = df[background_only_mask | transgenic_mask].copy()
    df["background_only"] = background_only_mask.loc[df.index].fillna(False)

    print(f"[v10_load_fish_lines] candidate rows after stage/background/base filters: {len(df)}")
    if df.empty:
        print("[v10_load_fish_lines] no candidate rows after filters; exiting.")
        return

    engine = get_engine(args.db_url)
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

    df["construct_id"] = None
    df["construct_code_canon"] = None

    missing_construct = 0
    missing_codes: set[str] = set()

    for idx, row in df.iterrows():
        if row["background_only"]:
            continue
        code = row["base_code_raw"]
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

    df = df[df["background_only"] | df["construct_id"].notna()].copy()

    if df.empty:
        print("[v10_load_fish_lines] after construct resolution, no rows remain; exiting.")
        return

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

    stage_rank: Dict[str, int] = {
        "stable": 0,
        "founder": 1,
        "f2": 2,
        "f1": 3,
        "p0": 4,
    }

    inserted_lines = 0
    inserted_alleles = 0
    skipped_alloc = 0

    with engine.begin() as cx:
        # 1) Build seed groups: natural lines keyed by (nickname, background, stage)
        seed_groups: List[Dict[str, Any]] = []
        for (nick_key, bg_key, stage_key), sub in df.groupby(["nick_key", "bg_key", "stage_key"], sort=False):
            if sub.empty:
                continue
            g: Dict[str, Any] = {
                "nick_key": nick_key,
                "bg_key": bg_key,
                "stage_key": stage_key,
                "nickname": str(sub["nickname"].iloc[0]).strip(),
                "bg": str(sub["genetic_background"].iloc[0]).strip(),
                "stage": str(sub["line_building_stage"].iloc[0]).strip(),
                "rows": [],
            }
            for _, r in sub.iterrows():
                g["rows"].append(
                    {
                        "construct_id": None if pd.isna(r["construct_id"]) else str(r["construct_id"]).strip(),
                        "construct_code_canon": (r["construct_code_canon"] or "").strip()
                        if r["construct_code_canon"] is not None
                        else "",
                        "allele_nickname": (r["allele_nickname"] or "").strip(),
                        "zygosity": None if pd.isna(r["zygosity"]) else str(r["zygosity"]).strip(),
                        "background_only": bool(r["background_only"]),
                    }
                )
            seed_groups.append(g)

        # 2) Genotype-keyed groups: (bg_key, geno_key) => canonical line + allele set
        geno_groups: Dict[Tuple[str, str], Dict[str, Any]] = {}

        alloc_cache: Dict[Tuple[str, str], Optional[Tuple[str, int]]] = {}

        for g in seed_groups:
            bg_key = g["bg_key"]
            stage_key = g["stage_key"]
            nickname = g["nickname"]
            bg = g["bg"]

            allele_tokens: List[str] = []
            allele_records: List[Tuple[str, str, int, Optional[str]]] = []

            all_bg_only = True
            for row in g["rows"]:
                if row["background_only"]:
                    continue
                all_bg_only = False
                canon_code = row["construct_code_canon"]
                if not canon_code:
                    continue
                allele_nick = row["allele_nickname"]
                key = (canon_code, allele_nick)
                if key in alloc_cache:
                    alloc = alloc_cache[key]
                else:
                    res = cx.execute(
                        ensure_sql,
                        {"construct_code": canon_code, "allele_nickname": allele_nick},
                    ).fetchone()
                    if res is None:
                        print(
                            f"[v10_load_fish_lines] WARN: allocator returned no row for construct_code={canon_code}, nick={allele_nick}"
                        )
                        alloc = None
                    else:
                        alloc = (
                            str(res._mapping["transgene_base"],).strip()
                            if "transgene_base" in res._mapping
                            else str(res._mapping["transgene_base_code"]).strip()
                        ), int(res._mapping["allele_number"])
                    alloc_cache[key] = alloc

                if alloc is None:
                    skipped_alloc += 1
                    continue

                tbase, anum = alloc
                zyg = row["zygosity"] or ""
                token = f"{tbase}#{anum}#{zyg}"
                allele_tokens.append(token)
                allele_records.append((row["construct_id"], tbase, anum, zyg))

            if all_bg_only or not allele_tokens:
                geno_key = f"BG:{bg_key}"
                allele_set: List[Tuple[str, str, int, Optional[str]]] = []
            else:
                unique_tokens = sorted(set(allele_tokens))
                geno_key = "||".join(unique_tokens)
                allele_set = allele_records

            gid = (bg_key, geno_key)
            if gid not in geno_groups:
                geno_groups[gid] = {
                    "bg": bg,
                    "nickname": nickname,
                    "stage": g["stage"],
                    "stage_rank": stage_rank.get(stage_key, 999),
                    "alleles": set(allele_set),
                }
            else:
                grp = geno_groups[gid]
                rank = stage_rank.get(stage_key, 999)
                if rank < grp["stage_rank"]:
                    grp["stage_rank"] = rank
                    grp["stage"] = g["stage"]
                    grp["nickname"] = nickname or grp["nickname"]
                grp["alleles"].update(allele_set)

        print(f"[v10_load_fish_lines] genotype groups: {len(geno_groups)}")

        # 3) Insert one fish_lines row per genotype, plus its allele set
        for (bg_key, geno_key), info in geno_groups.items():
            nickname = info["nickname"]
            bg = info["bg"]
            stage = info["stage"]

            line_code = f"LINE-{hash(bg_key + '|' + geno_key) & 0xffffffff:08x}"
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

            for construct_id, tbase, anum, zygosity in info["alleles"]:
                if not construct_id or anum is None:
                    continue
                cx.execute(
                    insert_jla,
                    {
                        "line_id": line_id,
                        "construct_id": construct_id,
                        "allele_number": anum,
                        "zygosity": zygosity or None,
                    },
                )
                inserted_alleles += 1

    print(f"[v10_load_fish_lines] inserted {inserted_lines} fish_lines")
    print(f"[v10_load_fish_lines] linked {inserted_alleles} allele rows for lines")
    print(f"[v10_load_fish_lines] skipped {skipped_alloc} allocator call(s)")


if __name__ == "__main__":
    main()