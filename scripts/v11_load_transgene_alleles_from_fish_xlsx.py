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


def get_engine():
    url = os.environ.get("DB_URL")
    if not url:
        raise SystemExit("DB_URL is not set")
    return create_engine(url)


def load_construct_lut(cx) -> dict[str, str]:
    """
    Rebuilds the construct LUT logic from v10_load_fish_lines_from_fish_xlsx.py,
    mapping various raw codes/aliases to canonical base_code.
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
        for raw in [
            r["construct_code"],
            r["base_code"],
            r["code_normalized"],
            r["alias"],
        ]:
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
        raise SystemExit(f"[v11_load_transgene_alleles_from_fish_xlsx] fish.xlsx not found at {path}")

    df = pd.read_excel(path)

    # Expected columns in fish.xlsx (from your sample):
    # nickname, birthday, genetic_background, line_building_stage,
    # transgene_base_code, allele_nickname, zygosity, created_by, description
    if "transgene_base_code" not in df.columns and "allele_nickname" not in df.columns:
        raise SystemExit(
            "[v11_load_transgene_alleles_from_fish_xlsx] fish.xlsx missing transgene_base_code / allele_nickname columns"
        )

    df = df.copy()
    df["transgene_base_code"] = df.get("transgene_base_code", "").map(norm)
    df["allele_nickname"] = df.get("allele_nickname", "").map(lambda s: norm(s))  # always string

    # Keep rows where we have either a transgene code or an allele nickname
    df = df[(df["transgene_base_code"] != "") | (df["allele_nickname"] != "")]
    if df.empty:
        print("[v11_load_transgene_alleles_from_fish_xlsx] no rows with transgene_base_code or allele_nickname; nothing to do")
        return

    created_alleles = 0
    reused_alleles = 0
    missing_constructs: set[str] = set()

    with engine.begin() as cx:
        # Build LUT for canonical construct base_codes
        lut = load_construct_lut(cx)

        # Get canonical construct base_codes for quick existence check
        df_constructs = pd.read_sql(
            text("SELECT base_code FROM public.constructs"),
            cx,
        )
        construct_codes = set(df_constructs["base_code"].map(norm))

        for _, row in df.iterrows():
            raw_code = row["transgene_base_code"]
            raw_nick = row["allele_nickname"]

            # Skip rows that are truly empty
            if not raw_code and not raw_nick:
                continue

            # Resolve canonical base_code using LUT if possible
            base_code = ""
            if raw_code:
                k = norm(raw_code)
                k_lc = k.lower()
                k_ns = k.replace(" ", "").replace("-", "")
                base_code = (
                    lut.get(k)
                    or lut.get(k_lc)
                    or lut.get(k_ns)
                    or lut.get(k_ns.lower())
                    or lut.get(k.upper())
                    or k  # last resort: use as-is
                )
            else:
                # No transgene_base_code; we can't mint allele without a base_code
                continue

            base_code = norm(base_code)
            if base_code not in construct_codes:
                missing_constructs.add(base_code)
                continue

            allele_nickname = raw_nick  # already normalized string

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

            # If we have a nickname, try to reuse an existing allele
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
                existing = res.fetchone()
                if existing:
                    # existing is a tuple: (allele_number, allele_name)
                    allele_number = int(existing[0])
                    allele_name = existing[1]
                    reused_alleles += 1

            # If not found, mint a new allele_number and allele_name
            if allele_number is None:
                seq_res = cx.execute(
                    text("SELECT nextval('public.transgene_alleles_allele_number_seq') AS n;")
                )
                allele_number = int(seq_res.scalar())
                allele_name = f"gu{allele_number}"

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

    if missing_constructs:
        print(
            "[v11_load_transgene_alleles_from_fish_xlsx] WARN: canonical base_code not found in constructs (skipped):",
            ", ".join(sorted(missing_constructs)),
        )

    print(
        f"[v11_load_transgene_alleles_from_fish_xlsx] created {created_alleles} alleles, reused {reused_alleles}"
    )


if __name__ == "__main__":
    main()
