#!/usr/bin/env python3
from __future__ import annotations
import os
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text


FISH_XLSX = "seed_kits/2025-11-15-121231-autoload/fish.xlsx"


def norm(s: object) -> str:
    if s is None:
        return ""
    return str(s).strip()


def norm_stage(s: object) -> str | None:
    x = norm(s).lower()
    if x in ("injection", "injections"):
        return "injections"
    if x in ("p0", "p-0"):
        return "p0"
    if x in ("f1", "f-1"):
        return "f1"
    if x in ("f2", "f-2"):
        return "f2"
    if x in ("stable",):
        return "stable"
    if x in ("founder",):
        return "founder"
    return x or None


def get_engine():
    url = os.environ.get("DB_URL")
    if not url:
        raise SystemExit("DB_URL is not set")
    return create_engine(url)


def load_construct_lut(cx) -> dict[str, str]:
    """
    Map raw transgene_base_code/plasmid labels to canonical constructs.base_code,
    same idea as v10_load_fish_lines_from_fish_xlsx.
    """
    df = pd.read_sql(
        text(
            """
            SELECT
              c.id::text        AS construct_id,
              c.construct_code  AS construct_code,
              c.base_code       AS base_code,
              vc.code_normalized,
              vc.alias
            FROM public.constructs c
            LEFT JOIN public.v_construct_codes_normalized vc
              ON vc.construct_id = c.id
            """
        ),
        cx,
    )
    lut: dict[str, str] = {}
    for _, r in df.iterrows():
        base = norm(r["base_code"]) or norm(r["construct_code"])
        if not base:
            continue
        keys = set()
        for raw in [r["construct_code"], r["base_code"], r["code_normalized"], r["alias"]]:
            k = norm(raw)
            if not k:
                continue
            keys.add(k)
            keys.add(k.lower())
            k_ns = k.replace(" ", "").replace("-", "")
            if k_ns:
                keys.add(k_ns)
        for k in keys:
            lut[k] = base
    return lut


def main() -> None:
    engine = get_engine()
    path = Path(FISH_XLSX)
    if not path.exists():
        raise SystemExit(f"[v11_seed_fish_transgene_alleles_from_fish_xlsx] fish.xlsx not found: {path}")

    # 1) Load fish.xlsx
    df_src = pd.read_excel(path)

    for col in ["nickname", "genetic_background", "line_building_stage", "transgene_base_code", "allele_nickname"]:
        if col not in df_src.columns:
            df_src[col] = ""
    df_src = df_src.copy()
    df_src["nickname"] = df_src["nickname"].map(norm)
    df_src["genetic_background"] = df_src["genetic_background"].map(norm)
    df_src["stage"] = df_src["line_building_stage"].map(norm_stage)
    df_src["raw_base_code"] = df_src["transgene_base_code"].map(norm)
    df_src["allele_nickname"] = df_src["allele_nickname"].map(lambda s: norm(s))  # always string

    if "birthday" in df_src.columns:
        df_src["birthday"] = pd.to_datetime(df_src["birthday"]).dt.date
    else:
        df_src["birthday"] = pd.NaT

    # We only keep rows that have a base_code, a stage, and a birthday
    df_src = df_src[
        (df_src["raw_base_code"] != "")
        & df_src["stage"].notna()
        & df_src["birthday"].notna()
    ].copy()
    if df_src.empty:
        print("[v11_seed_fish_transgene_alleles_from_fish_xlsx] no usable rows; nothing to do")
        return

    inserted_links = 0
    skipped_mismatch_clusters = 0
    missing_constructs: set[str] = set()
    missing_alleles: set[tuple[str, str]] = set()

    with engine.begin() as cx:
        # 2) Construct LUT & valid base_codes
        lut_constructs = load_construct_lut(cx)
        df_constructs = pd.read_sql(text("SELECT base_code FROM public.constructs"), cx)
        construct_codes = set(df_constructs["base_code"].map(norm))

        # 3) Allele LUT from transgene_alleles (base_code + allele_nickname → allele_number)
        df_alleles = pd.read_sql(
            text(
                """
                SELECT
                  transgene_base_code,
                  allele_number,
                  allele_name,
                  allele_nickname
                FROM public.transgene_alleles
                """
            ),
            cx,
        )
        allele_lut: dict[tuple[str, str], int] = {}
        for _, r in df_alleles.iterrows():
            bc = norm(r["transgene_base_code"])
            nick = norm(r["allele_nickname"])  # '' if null
            key = (bc, nick)
            allele_lut[key] = int(r["allele_number"])

        # 4) Fish instances with line nicknames & stages
        df_inst = pd.read_sql(
            text(
                """
                SELECT
                  fi.id::text      AS fish_id,
                  fi.fish_code,
                  fi.birthday      AS birthday,
                  fi.instance_stage,
                  fl.nickname      AS line_nickname,
                  fl.genetic_background
                FROM public.fish_instances_v10 fi
                JOIN public.fish_lines fl
                  ON fl.id = fi.line_id
                """
            ),
            cx,
        )
        df_inst["line_nickname"] = df_inst["line_nickname"].map(norm)
        df_inst["genetic_background"] = df_inst["genetic_background"].map(norm)
        df_inst["inst_stage"] = df_inst["instance_stage"].map(norm_stage)
        df_inst["birthday"] = pd.to_datetime(df_inst["birthday"]).dt.date

        # 5) Canonical base_code for df_src
        def resolve_base(raw: str) -> str:
            if not raw:
                return ""
            k = raw
            k_lc = k.lower()
            k_ns = k.replace(" ", "").replace("-", "")
            return (
                norm(
                    lut_constructs.get(k)
                    or lut_constructs.get(k_lc)
                    or lut_constructs.get(k_ns)
                    or lut_constructs.get(k_ns.lower())
                    or lut_constructs.get(k.upper())
                    or k
                )
            )

        df_src["base_code"] = df_src["raw_base_code"].map(resolve_base)

        # 6) Cluster by (nickname, background, stage, birthday, base_code)
        df_src["key_nick"] = df_src["nickname"]
        df_src["key_bg"] = df_src["genetic_background"]
        df_src["key_stage"] = df_src["stage"]
        df_src["key_bday"] = df_src["birthday"]

        df_inst["key_nick"] = df_inst["line_nickname"]
        df_inst["key_bg"] = df_inst["genetic_background"]
        df_inst["key_stage"] = df_inst["inst_stage"]
        df_inst["key_bday"] = df_inst["birthday"]

        cluster_cols = ["key_nick", "key_bg", "key_stage", "key_bday", "base_code"]

        for cluster_key, df_cluster in df_src.groupby(cluster_cols):
            key_nick, key_bg, key_stage, key_bday, base_code = cluster_key
            if base_code not in construct_codes:
                missing_constructs.add(base_code)
                continue

            # allele rows (one per conceptual fish) in fish.xlsx
            df_cluster_valid = df_cluster.copy()
            # total rows (including repeated allele_nickname) define conceptual individuals
            src_rows = df_cluster_valid.sort_values(
                by=["allele_nickname", "birthday", "raw_base_code"]
            )

            # matching fish_instances
            mask_inst = (
                (df_inst["key_nick"] == key_nick)
                & (df_inst["key_bg"] == key_bg)
                & (df_inst["key_stage"] == key_stage)
                & (df_inst["key_bday"] == key_bday)
            )
            inst_rows = df_inst[mask_inst].copy().sort_values(by=["fish_code"])

            n_src = len(src_rows)
            n_inst = len(inst_rows)

            if n_src != n_inst:
                # Without 1:1 cardinality, we cannot safely assign alleles per fish; skip
                skipped_mismatch_clusters += 1
                continue

            # Pair each fish_instance with one fish.xlsx row (one allele_nickname)
            for (_, row_src), (_, row_inst) in zip(src_rows.iterrows(), inst_rows.iterrows()):
                allele_nickname = norm(row_src["allele_nickname"])
                key_allele = (base_code, allele_nickname)
                allele_number = allele_lut.get(key_allele)
                if allele_number is None:
                    missing_alleles.add(key_allele)
                    continue

                fish_id = row_inst["fish_id"]

                res = cx.execute(
                    text(
                        """
                        INSERT INTO public.fish_transgene_alleles (
                          fish_id,
                          transgene_base_code,
                          allele_number
                        ) VALUES (
                          :fid,
                          :bc,
                          :anum
                        )
                        ON CONFLICT (fish_id, transgene_base_code, allele_number) DO NOTHING;
                        """
                    ),
                    {"fid": fish_id, "bc": base_code, "anum": int(allele_number)},
                )
                inserted_links += res.rowcount

    if missing_constructs:
        print(
            "[v11_seed_fish_transgene_alleles_from_fish_xlsx] WARN: canonical base_code not in constructs (skipped clusters):",
            ", ".join(sorted(missing_constructs)),
        )
    if missing_alleles:
        print(
            "[v11_seed_fish_transgene_alleles_from_fish_xlsx] WARN: allele (base_code, nickname) missing in transgene_alleles (skipped):",
            ", ".join(f"{bc}:{nick}" for bc, nick in sorted(missing_alleles)),
        )
    if skipped_mismatch_clusters:
        print(
            f"[v11_seed_fish_transgene_alleles_from_fish_xlsx] WARN: skipped {skipped_mismatch_clusters} cluster(s) due to row-count mismatch between fish.xlsx and fish_instances."
        )

    print(
        f"[v11_seed_fish_transgene_alleles_from_fish_xlsx] inserted {inserted_links} fish_transgene_alleles links"
    )


if __name__ == "__main__":
    main()
