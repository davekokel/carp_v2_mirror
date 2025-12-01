#!/usr/bin/env python3
from __future__ import annotations
import os
from sqlalchemy import create_engine, text
import pandas as pd

def norm(s) -> str:
    if s is None:
        return ""
    return str(s).strip()

def get_engine():
    url = os.environ.get("DB_URL")
    if not url:
        raise SystemExit("DB_URL is not set")
    return create_engine(url)

def main() -> None:
    engine = get_engine()

    with engine.begin() as cx:
        # 1) Pull fish_instances + their line construct_code
        df = pd.read_sql(
            text(
                """
                SELECT
                  fi.id::text        AS fish_id,
                  fi.fish_code,
                  fl.construct_code  AS line_construct_code
                FROM public.fish_instances_v10 fi
                JOIN public.fish_lines fl
                  ON fl.id = fi.line_id
                """
            ),
            cx,
        )

    df["line_construct_code"] = df["line_construct_code"].map(norm)
    df["fish_code"] = df["fish_code"].map(norm)
    df = df[(df["line_construct_code"] != "") & (df["fish_code"] != "")]
    if df.empty:
        print("[v11_seed_fish_transgene_alleles_from_lines] no fish with line_construct_code; nothing to do")
        return

    # Drop duplicates so we only seed one allele per (fish, construct_code)
    df = df.drop_duplicates(subset=["fish_id", "line_construct_code"]).copy()

    engine = get_engine()
    missing_constructs = set()
    inserted_transgenes = 0
    inserted_alleles = 0
    inserted_links = 0

    with engine.begin() as cx:
        # Build LUT of constructs.base_code so we can sanity-check
        constructs = pd.read_sql(
            text("SELECT base_code FROM public.constructs"),
            cx,
        )
        basecodes = set(constructs["base_code"].map(norm))

        for _, row in df.iterrows():
            fish_id = row["fish_id"]
            base_code = row["line_construct_code"]

            if base_code not in basecodes:
                missing_constructs.add(base_code)
                continue

            # 2) Ensure transgene exists (transgene_base_code FK -> constructs.base_code)
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
            inserted_transgenes += 1

            # 3) Ensure allele exists (we start with allele_number = 1)
            cx.execute(
                text(
                    """
                    INSERT INTO public.transgene_alleles (transgene_base_code, allele_number, allele_name)
                    VALUES (:bc, 1, NULL)
                    ON CONFLICT (transgene_base_code, allele_number) DO NOTHING;
                    """
                ),
                {"bc": base_code},
            )
            inserted_alleles += 1

            # 4) Link fish to allele
            res = cx.execute(
                text(
                    """
                    INSERT INTO public.fish_transgene_alleles (fish_id, transgene_base_code, allele_number)
                    VALUES (:fish_id, :bc, 1)
                    ON CONFLICT (fish_id, transgene_base_code, allele_number) DO NOTHING;
                    """
                ),
                {"fish_id": fish_id, "bc": base_code},
            )
            inserted_links += res.rowcount

    if missing_constructs:
        print(
            "[v11_seed_fish_transgene_alleles_from_lines] WARN: line_construct_code not found in constructs (skipped):",
            ", ".join(sorted(missing_constructs)),
        )

    print(
        f"[v11_seed_fish_transgene_alleles_from_lines] ensured transgenes ~{inserted_transgenes}, "
        f"alleles ~{inserted_alleles}, links {inserted_links}"
    )

if __name__ == "__main__":
    main()
