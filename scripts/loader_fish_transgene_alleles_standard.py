import os
import pathlib

import pandas as pd
from sqlalchemy import create_engine, text


FISH_XLSX_DEFAULT = "seed_kits/2025-11-15-121231-autoload/fish.xlsx"


def make_genotype_code(transgene_base_code, allele_nickname):
    if pd.isna(transgene_base_code) or pd.isna(allele_nickname):
        return None
    base = str(transgene_base_code).strip()
    nick = str(allele_nickname).strip()
    if not base or not nick:
        return None
    base_norm = base.replace("-", "_")
    return f"GT_STD_{base_norm}_{nick}"


def load_fish_genotypes(engine, fish_xlsx: pathlib.Path) -> None:
    df = pd.read_excel(fish_xlsx)

    if "birthday" not in df.columns or "nickname" not in df.columns:
        raise SystemExit("fish.xlsx must contain 'birthday' and 'nickname' columns")

    if "transgene_base_code" not in df.columns or "allele_nickname" not in df.columns:
        raise SystemExit("fish.xlsx must contain 'transgene_base_code' and 'allele_nickname' columns")

    df = df.copy()
    df["genotype_code"] = [
        make_genotype_code(tb, an)
        for tb, an in zip(df["transgene_base_code"], df["allele_nickname"])
    ]

    df = df.dropna(subset=["genotype_code"])

    linked = 0

    with engine.begin() as cx:
        for _, row in df.iterrows():
            birthday = pd.to_datetime(row["birthday"]).date()
            nickname = str(row["nickname"]).strip()
            genotype_code = row["genotype_code"]

            fish_id = cx.execute(
                text(
                    """
                    SELECT id
                    FROM public.fish_instance
                    WHERE birthday = :birthday
                      AND nickname = :nickname
                    ORDER BY created_at
                    LIMIT 1
                    """
                ),
                {"birthday": birthday, "nickname": nickname},
            ).scalar()

            if fish_id is None:
                continue

            genotype_id = cx.execute(
                text(
                    """
                    SELECT id
                    FROM public.genotypes
                    WHERE genotype_code = :genotype_code
                    """
                ),
                {"genotype_code": genotype_code},
            ).scalar()

            if genotype_id is None:
                continue

            cx.execute(
                text(
                    """
                    INSERT INTO public.join_fish_genotypes (fish_id, genotype_id)
                    VALUES (:fish_id, :genotype_id)
                    ON CONFLICT DO NOTHING
                    """
                ),
                {"fish_id": fish_id, "genotype_id": genotype_id},
            )
            linked += 1

    print(f"join_fish_genotypes rows linked from {fish_xlsx}: {linked}")


def populate_join_fish_transgene_alleles(engine) -> None:
    with engine.begin() as cx:
        cx.execute(text("DELETE FROM public.join_fish_transgene_alleles"))

        cx.execute(
            text(
                """
                INSERT INTO public.join_fish_transgene_alleles
                  (fish_id, transgene_base_code, allele_number, zygosity)
                SELECT
                  jfg.fish_id,
                  jgta.transgene_base_code,
                  jgta.allele_number,
                  jgta.zygosity
                FROM public.join_fish_genotypes jfg
                JOIN public.join_genotype_transgene_alleles jgta
                  ON jgta.genotype_id = jfg.genotype_id
                """
            )
        )

        counts = cx.execute(
            text(
                """
                SELECT 'join_fish_genotypes' AS table_name, COUNT(*) FROM public.join_fish_genotypes
                UNION ALL
                SELECT 'join_genotype_transgene_alleles', COUNT(*) FROM public.join_genotype_transgene_alleles
                UNION ALL
                SELECT 'join_fish_transgene_alleles', COUNT(*) FROM public.join_fish_transgene_alleles
                """
            )
        ).fetchall()

    for table_name, count in counts:
        print(f"{table_name}: {count}")


def main() -> None:
    db_url = os.environ.get("DB_URL")
    if not db_url:
        raise SystemExit("DB_URL environment variable is required")

    engine = create_engine(db_url)

    fish_xlsx_env = os.environ.get("FISH_XLSX")
    fish_xlsx = pathlib.Path(fish_xlsx_env or FISH_XLSX_DEFAULT)

    if not fish_xlsx.exists():
        raise SystemExit(f"fish.xlsx not found at {fish_xlsx}")

    print(f"Using DB_URL={db_url}")
    print(f"Using fish.xlsx={fish_xlsx}")

    load_fish_genotypes(engine, fish_xlsx)
    populate_join_fish_transgene_alleles(engine)


if __name__ == "__main__":
    main()
