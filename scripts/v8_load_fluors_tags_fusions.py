import os
import argparse
from typing import Tuple

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


def get_engine() -> Engine:
    db_url = os.environ.get("DB_URL")
    if not db_url:
        raise RuntimeError("DB_URL environment variable is not set")
    print(f"DB_URL={db_url}")
    return create_engine(db_url)


def upsert_fluors(engine: Engine, df: pd.DataFrame) -> Tuple[int, int]:
    inserted = 0
    updated = 0

    # Your CSV has: nickname, excitation_nm, emission_nm, note, aliases
    required_cols = {"nickname", "excitation_nm", "emission_nm"}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"fluors CSV is missing required columns: {missing}")

    sql = text(
        """
        INSERT INTO public.fluors (
          fluor_code,
          fluor_name,
          excitation_nm,
          emission_nm
        )
        VALUES (
          :fluor_code,
          :fluor_name,
          :excitation_nm,
          :emission_nm
        )
        ON CONFLICT (fluor_code) DO UPDATE
        SET
          fluor_name    = EXCLUDED.fluor_name,
          excitation_nm = EXCLUDED.excitation_nm,
          emission_nm   = EXCLUDED.emission_nm
        """
    )

    with engine.begin() as cx:
        for _, row in df.iterrows():
            nickname = str(row["nickname"]).strip()
            if not nickname:
                continue

            excitation = int(row["excitation_nm"]) if pd.notna(row["excitation_nm"]) else None
            emission = int(row["emission_nm"]) if pd.notna(row["emission_nm"]) else None

            params = {
                "fluor_code": nickname,
                "fluor_name": nickname,  # for now, use nickname as display name too
                "excitation_nm": excitation,
                "emission_nm": emission,
            }
            cx.execute(sql, params)
            inserted += 1

    return inserted, updated


def upsert_tags(engine: Engine, df: pd.DataFrame) -> Tuple[int, int]:
    inserted = 0
    updated = 0

    # tags.xlsx: nickname, localization, note, citation_link, aliases
    required_cols = {"nickname"}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"tags file is missing required columns: {missing}")

    sql = text(
        """
        INSERT INTO public.tags (tag_code, tag_name, localization, notes)
        VALUES (:tag_code, :tag_name, :localization, :notes)
        ON CONFLICT (tag_code) DO UPDATE
        SET tag_name    = EXCLUDED.tag_name,
            localization = EXCLUDED.localization,
            notes        = EXCLUDED.notes
        """
    )

    with engine.begin() as cx:
        for _, row in df.iterrows():
            nickname = str(row["nickname"]).strip()
            if not nickname:
                continue

            localization = str(row.get("localization") or "").strip() or None
            note = str(row.get("note") or "").strip() or None

            params = {
                "tag_code": nickname,
                "tag_name": nickname,  # nickname doubles as name
                "localization": localization,
                "notes": note,
            }
            cx.execute(sql, params)
            inserted += 1  # count rows we upserted

    return inserted, updated


def upsert_fusions(engine: Engine, df: pd.DataFrame) -> Tuple[int, int]:
    inserted = 0
    updated = 0

    required_cols = {"fusion_code", "fluor_code", "tag_code"}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"fusions CSV is missing required columns: {missing}")

    fusion_sql = text(
        """
        INSERT INTO public.fusions (fusion_code, fluor_id, tag_id, description)
        VALUES (:fusion_code, :fluor_id, :tag_id, :description)
        ON CONFLICT (fusion_code) DO UPDATE
        SET
          fluor_id    = EXCLUDED.fluor_id,
          tag_id      = EXCLUDED.tag_id,
          description = EXCLUDED.description
        """
    )

    fluor_lookup_sql = text(
        "SELECT id FROM public.fluors WHERE fluor_code = :fluor_code"
    )
    tag_lookup_sql = text(
        "SELECT id FROM public.tags WHERE tag_code = :tag_code"
    )

    with engine.begin() as cx:
        for _, row in df.iterrows():
            fusion_code = str(row["fusion_code"]).strip()
            fluor_code = str(row["fluor_code"]).strip() if pd.notna(row["fluor_code"]) else None
            tag_code = str(row["tag_code"]).strip() if pd.notna(row["tag_code"]) else None
            description = (
                str(row["description"]).strip()
                if "description" in df.columns and pd.notna(row["description"])
                else None
            )

            fluor_id = None
            tag_id = None

            if fluor_code:
                fluor_id = cx.execute(fluor_lookup_sql, {"fluor_code": fluor_code}).scalar()
                if fluor_id is None:
                    raise RuntimeError(
                        f"Fusion {fusion_code}: fluor_code '{fluor_code}' not found in public.fluors"
                    )

            if tag_code:
                tag_id = cx.execute(tag_lookup_sql, {"tag_code": tag_code}).scalar()
                if tag_id is None:
                    raise RuntimeError(
                        f"Fusion {fusion_code}: tag_code '{tag_code}' not found in public.tags"
                    )

            params = {
                "fusion_code": fusion_code,
                "fluor_id": fluor_id,
                "tag_id": tag_id,
                "description": description,
            }
            cx.execute(fusion_sql, params)
            inserted += 1

    return inserted, updated


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Load v8 fluors, tags, and (optionally) fusions into CARP."
    )
    parser.add_argument("--fluors-csv", required=True, help="Path to fluors CSV file")
    parser.add_argument("--tags-file", required=True, help="Path to tags CSV/XLSX file")
    parser.add_argument(
        "--fusions-csv",
        required=False,
        help="Path to fusions CSV file (optional; skip if not provided)",
    )
    args = parser.parse_args()

    engine = get_engine()

    df_fluors = pd.read_csv(args.fluors_csv)
    df_tags = (
        pd.read_excel(args.tags_file)
        if args.tags_file.lower().endswith((".xlsx", ".xls"))
        else pd.read_csv(args.tags_file)
    )

    ins_fluors, _ = upsert_fluors(engine, df_fluors)
    print(f"fluors: handled={ins_fluors}")

    ins_tags, _ = upsert_tags(engine, df_tags)
    print(f"tags:   handled={ins_tags}")

    if args.fusions_csv:
        if not os.path.exists(args.fusions_csv):
            raise FileNotFoundError(f"fusions CSV not found: {args.fusions_csv}")
        df_fusions = pd.read_csv(args.fusions_csv)
        ins_fusions, _ = upsert_fusions(engine, df_fusions)
        print(f"fusions: handled={ins_fusions}")
    else:
        print("fusions: skipped (no --fusions-csv provided)")


if __name__ == "__main__":
    main()
