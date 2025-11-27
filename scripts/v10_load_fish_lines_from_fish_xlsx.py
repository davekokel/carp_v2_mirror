from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Optional, Dict, Tuple, List

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
        cid = str(row["construct_id"]).strip()
        code = (row["construct_code"] or "").strip()
        base = (row["base_code"] or "").strip()
        alias = (row.get("alias") or "").strip()
        canon = code or base

        keys = set()
        if code:
            keys.add(code)
        if base:
            keys.add(base)
        if alias:
            keys.add(alias)

        for k in keys:
            if not k:
                continue
            lookup[k] = (cid, canon or k)
            lookup[k.lower()] = (cid, canon or k.lower())

    print(f"[v10_load_fish_lines] construct lookup keys: {len(lookup)}")
    return lookup


def main() -> None:
    print("[v10_load_fish_lines] START")
    parser = argparse.ArgumentParser(
        description="v10: load fish_lines + join_line_alleles from fish.xlsx (genotype-based)."
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

    required = [
        "nickname",
        "birthday",
        "genetic_background",
        "line_building_stage",
        "transgene_base_code",
        "allele_nickname",
        "zygosity",
    ]
    missing = [c for c in required if c not in df.columns]
    if missing:
        print(f"[v10_load_fish_lines] missing columns: {missing}; exiting.")
        return

    df = df.copy()
    df["birthday"] = pd.to_datetime(df["birthday"], errors="coerce").dt.date
    df["transgene_base_code"] = df["transgene_base_code"].astype(str)
    df["allele_nickname"] = df["allele_nickname"].astype(str)

    df["nick_key"] = df["nickname"].apply(norm)
    df["bg_key"] = df["genetic_background"].apply(norm)
    df["stage_key"] = df["line_building_stage"].apply(norm)

    print("[v10_load_fish_lines] stage_key value_counts:")
    print(
        df["stage_key"].value_plots(dropna=False).to_string()
        if hasattr(df["stage_key"], "value_plots")
        else df["stage_key"].value_counts(dropna=False).to_string()
    )

    mask_stage = df["stage_key"].isin(["p0", "f1", "f2", "founder", "stable"])
    df = df[mask_stage].copy()
    if df.empty:
        print("[v10_load_fish_lines] no rows after stage filter; exiting.")
        return

    df["has_real_base"] = df["transgene_base_code"].apply(is_real_basecode)
    df = df[df["has_real_base"]].copy()
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
    missing_codes = set()

    for idx, code in df["transgene_base_code"].items():
        cid, canon = resolve_construct(str(code))
        if cid is None or not canon:
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

    engine = get_engine(args.db_url)

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

    geno_atoms: List[Tuple[str, str, str]] = []
    skipped_alloc = 0

    with engine.begin() as cx:
        for _, row in df.iterrows():
            canon = str(row["construct_code_canon"]).strip()
            allele = (row["allele_nickname"] or "").strip()
            if not canon:
                geno_atoms.append((None, None, None))  # type: ignore
                continue
            res = cx.execute(
                ensure_sql,
                {"construct_code": canon, "allele_nickname": allele},
            ).fetchone()
            if res is None:
                skipped_alloc += 1
                geno_atoms.append((None, None, None))  # type: ignore
                continue
            tbase = (res._mapping["transgene_base_code"] or "").strip()
            anum = str(res._mapping["allele_number"])
            cid = str(row["construct_id"]).strip()
            geno_atoms.append((cid, tbase, anum))

    df[["cid", "tbase", "anum"]] = pd.DataFrame(geno_atoms, index=df.index)
    df = df[df["cid"].notna() & df["anum"].notna()].copy()
    if skipped_alloc:
        print(f"[v10_load_fish_lines] skipped {skipped_alloc} allocator call(s)")
    if df.empty:
        print("[v10_load_fish_lines] no rows with resolved alleles; exiting.")
        return

    # allele-level genotype atom (for lines)
    df["geno_atom"] = df["cid"].astype(str) + "#" + df["anum"].astype(str)
    df["bg_key"] = df["genetic_background"].apply(norm)

    def make_key(sub: pd.Series) -> str:
        vals = sorted(set(str(x) for x in sub if pd.notna(x)))
        return "||".join(vals)

    # allele-level genotype for lines
    geno_by_seed = df.groupby("nick_key").apply(
        lambda g: make_key(g["geno_atom"])
    )
    # basecode-level genotype for groups
    group_by_seed = df.groupby("nick_key").apply(
        lambda g: make_key(g["tbase"])
    )

    df = df.merge(
        geno_by_seed.rename("geno_key"),
        left_on="nick_key",
        right_index=True,
        how="left",
    )
    df = df.merge(
        group_by_seed.rename("group_key"),
        left_on="nick_key",
        right_index=True,
        how="left",
    )

    # lines: background + allele-level genotype
    df["line_key"] = df["bg_key"] + "|" + df["geno_key"]
    line_groups = df.groupby("line_key")

    print(f"[v10_load_fish_lines] genotype groups (lines): {len(line_groups)}")

    # groups: basecode-level genotype (group_key)
    ensure_group_sql = text(
        """
        INSERT INTO public.fish_groups (genotype_key, group_code)
        VALUES (
          :genotype_key,
          'GROUP-' || substr(gen_random_uuid()::text, 1, 8)
        )
        ON CONFLICT (genotype_key) DO UPDATE
          SET genotype_key = EXCLUDED.genotype_key
        RETURNING id::text AS fish_group_id, group_code
        """
    )

    insert_line_sql = text(
        """
        INSERT INTO public.fish_lines (
          line_code,
          nickname,
          genetic_background,
          line_building_stage,
          notes,
          fish_group_id,
          group_instance_code,
          created_at
        )
        VALUES (
          :line_code,
          :nickname,
          :bg,
          :stage,
          :notes,
          :fish_group_id,
          :group_instance_code,
          now()
        )
        RETURNING id::text AS line_id
        """
    )

    insert_group_allele_sql = text(
        """
        INSERT INTO public.join_fish_group_alleles (
          fish_group_id,
          construct_id,
          allele_number
        )
        VALUES (
          :fish_group_id,
          :construct_id,
          :allele_number
        )
        ON CONFLICT (fish_group_id, construct_id, allele_number) DO NOTHING
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

    group_counts: Dict[str, int] = {}

    with engine.begin() as cx:
        for key, sub in line_groups:
            bg = sub["genetic_background"].iloc[0]
            stage = sub["line_building_stage"].iloc[0]
            nickname = sub["nickname"].iloc[0]
            geno_key = sub["geno_key"].iloc[0]
            group_key = sub["group_key"].iloc[0]

            line_code = f"LINE-{hash(key) & 0xffffffff:08x}"

            # basecode-defined group
            grp_row = cx.execute(
                ensure_group_sql,
                {"genotype_key": group_key},
            ).fetchone()
            fish_group_id = grp_row._mapping["fish_group_id"]
            group_code = grp_row._mapping["group_code"]

            # populate group alleles (all alleles for all lines in this group)
            group_alleles = (
                sub[["cid", "anum"]]
                .dropna()
                .drop_duplicates(subset=["cid", "anum"])
            )
            for _, ga in group_alleles.iterrows():
                cid_ga = str(ga["cid"]).strip()
                anum_ga = int(str(ga["anum"]).strip())
                cx.execute(
                    insert_group_allele_sql,
                    {
                        "fish_group_id": fish_group_id,
                        "construct_id": cid_ga,
                        "allele_number": anum_ga,
                    },
                )

            group_counts[group_code] = group_counts.get(group_code, 0) + 1
            idx = group_counts[group_code]
            group_instance_code = f"{group_code}-{idx:03d}"

            print(
                f"[v10_load_fish_lines] inserting line "
                f"line_code={line_code} nickname={nickname!r} "
                f"bg={bg!r} stage={stage!r} geno_key={geno_key!r} "
                f"group_key={group_key!r} group_code={group_code!r} "
                f"group_instance_code={group_instance_code!r}"
            )

            res_line = cx.execute(
                insert_line_sql,
                {
                    "line_code": line_code,
                    "nickname": nickname,
                    "bg": bg,
                    "stage": stage,
                    "notes": None,
                    "fish_group_id": fish_group_id,
                    "group_instance_code": group_instance_code,
                },
            ).fetchone()
            if res_line is None:
                continue
            line_id = res_line._mapping["line_id"]
            inserted_lines += 1

            seen: set[Tuple[str, str, Optional[str]]] = set()
            for _, row in sub.iterrows():
                cid = str(row["cid"]).strip()
                anum = str(row["anum"]).strip()
                zyg = (row["zygosity"] or "").strip() or None
                atom = (cid, anum, zyg)
                if atom in seen:
                    continue
                seen.add(atom)
                cx.execute(
                    insert_jla,
                    {
                        "line_id": line_id,
                        "construct_id": cid,
                        "allele_number": int(anum),
                        "zygosity": zyg,
                    },
                )
                inserted_alleles += 1

    print(f"[v10_load_fish_lines] inserted {inserted_lines} fish_lines")
    print(f"[v10_load_fish_lines] linked {inserted_alleles} allele rows for lines")
    print(f"[v10_load_fish_lines] skipped {skipped_alloc} allocator call(s)")


if __name__ == "__main__":
    main()