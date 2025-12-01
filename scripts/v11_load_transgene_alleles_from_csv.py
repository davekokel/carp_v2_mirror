#!/usr/bin/env python3
from __future__ import annotations
import os
import argparse
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text


def norm(s: object) -> str:
    if s is None:
        return ""
    return str(s).strip()


def get_engine():
    url = os.environ.get("DB_URL")
    if not url:
        raise SystemExit("DB_URL is not set")
    return create_engine(url)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--csv",
        required=True,
        help="CSV with transgene_base_code, allele_nickname, and optional fish_code, zygosity",
    )
    args = p.parse_args()

    path = Path(args.csv)
    if not path.exists():
        raise SystemExit(f"[v11_load_transgene_alleles_from_csv] CSV not found: {path}")

    df = pd.read_csv(path)

    # Map logical fields to actual CSV columns (adjust here if names differ)
    col_map = {
        "transgene_base_code": None,
        "allele_nickname": None,
        "fish_code": None,
        "zygosity": None,
    }

    cols = set(df.columns)

    for key in ["transgene_base_code", "allele_nickname", "fish_code", "zygosity"]:
        if key in cols:
            col_map[key] = key

    if col_map["transgene_base_code"] is None:
        raise SystemExit(
            f"[v11_load_transgene_alleles_from_csv] missing required column 'transgene_base_code' in CSV with columns {list(df.columns)}"
        )

    # Always treat allele_nickname as string (even if numeric)
    if col_map["allele_nickname"] is None:
        df["allele_nickname"] = ""
        col_map["allele_nickname"] = "allele_nickname"

    df = df.copy()
    df["transgene_base_code"] = df[col_map["transgene_base_code"]].map(norm)
    df["allele_nickname"] = df[col_map["allele_nickname"]].map(
        lambda s: norm(s)
    )  # always string
    if col_map["fish_code"]:
        df["fish_code"] = df[col_map["fish_code"]].map(norm)
    else:
        df["fish_code"] = ""

    if col_map["zygosity"]:
        df["zygosity"] = df[col_map["zygosity"]].map(norm)
    else:
        df["zygosity"] = ""

    # Filter to rows with a base_code
    df = df[df["transgene_base_code"] != ""].copy()
    if df.empty:
        print("[v11_load_transgene_alleles_from_csv] no usable rows after filtering; nothing to do")
        return

    engine = get_engine()

    missing_constructs = set()
    missing_fish = set()
    created_alleles = 0
    reused_alleles = 0
    linked_fish = 0

    with engine.begin() as cx:
        # LUT: canonical constructs (for transgene_base_code normalization)
        df_constructs = pd.read_sql(
            text("SELECT base_code FROM public.constructs"),
            cx,
        )
        construct_codes = set(df_constructs["base_code"].map(norm))

        # LUT: fish_code → fish_id
        df_fish = pd.read_sql(
            text("SELECT id::text AS fish_id, fish_code FROM public.fish_instances_v10"),
            cx,
        )
        fish_lut = dict(zip(df_fish["fish_code"].map(norm), df_fish["fish_id"]))

        for _, row in df.iterrows():
            base_code_raw = row["transgene_base_code"]
            base_code = norm(base_code_raw)

            if base_code not in construct_codes:
                missing_constructs.add(base_code)
                continue

            allele_nickname = row["allele_nickname"]  # always string
            fish_code = row["fish_code"]
            zygosity = row["zygosity"] or None

            # Ensure transgene exists
            cx.execute(
                text(
                    """
                    INSERT INTO public.transgenes (transgene_base_code, description, transgene_name)
                    VALUES (:bc, NULL, :bc)
                    ON CONFLICT (transgene_base_code) DO NOTHING;
                    """
                ),
                {"bc": base_code},
            )

            # Try to find existing allele by base_code + allele_nickname (when nickname is non-empty)
            allele_number = None
            allele_name = None

            if allele_nickname:
                res = cx.execute(
                    text(
                        """
                        SELECT allele_number, allele_name
                        FROM public.transgene_alleles
                        WHERE transgene_base_code = :bc
                          AND allele_nickname = :nick
                        """
                    ),
                    {"bc": base_code, "nick": allele_nickname},
                )
                row_existing = res.fetchone()
                if row_existing:
                    allele_number = row_existing["allele_number"]
                    allele_name = row_existing["allele_name"]
                    reused_alleles += 1

            # If no existing allele found, mint a new one
            if allele_number is None:
                # Use the global sequence for allele_number
                res_seq = cx.execute(
                    text("SELECT nextval('public.transgene_alleles_allele_number_seq') AS n;")
                )
                allele_number = int(res_seq.scalar())
                allele_name = f"gu{allele_number}"

                # If nickname is empty, default nickname to allele_name
                final_nickname = allele_nickname if allele_nickname else allele_name

                cx.execute(
                    text(
                        """
                        INSERT INTO public.transgene_alleles (
                          transgene_base_code,
                          allele_number,
                          allele_name,
                          allele_nickname
                        ) VALUES (
                          :bc,
                          :num,
                          :aname,
                          :nick
                        )
                        ON CONFLICT (transgene_base_code, allele_number) DO NOTHING;
                        """
                    ),
                    {
                        "bc": base_code,
                        "num": allele_number,
                        "aname": allele_name,
                        "nick": final_nickname,
                    },
                )
                created_alleles += 1

            # Link to fish if fish_code is present
            if fish_code:
                fish_id = fish_lut.get(fish_code)
                if not fish_id:
                    missing_fish.add(fish_code)
                else:
                    res_link = cx.execute(
                        text(
                            """
                            INSERT INTO public.fish_transgene_alleles (
                              fish_id,
                              transgene_base_code,
                              allele_number,
                              zygosity
                            ) VALUES (
                              :fid,
                              :bc,
                              :num,
                              :zyg
                            )
                            ON CONFLICT (fish_id, transgene_base_code, allele_number) DO NOTHING;
                            """
                        ),
                        {
                            "fid": fish_id,
                            "bc": base_code,
                            "num": allele_number,
                            "zyg": zygosity,
                        },
                    )
                    linked_fish += res_link.rowcount

    if missing_constructs:
        print(
            "[v11_load_transgene_alleles_from_csv] WARN: transgene_base_code not found in constructs (skipped):",
            ", ".join(sorted(missing_constructs)),
        )
    if missing_fish:
        print(
            "[v11_load_transgene_alleles_from_csv] WARN: fish_code not found in fish_instances_v10 (skipped linking):",
            ", ".join(sorted(missing_fish)),
        )

    print(
        f"[v11_load_transgene_alleles_from_csv] created {created_alleles} alleles, reused {reused_alleles}, linked {linked_fish} fish_transgene_alleles rows"
    )

if __name__ == "__main__":
    main()
