import os
import argparse
from typing import Tuple, Dict

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
    """
    v11: upsert fluors using nickname/display_name.
    Expected CSV columns: nickname, excitation_nm, emission_nm.
    """
    inserted = 0
    updated = 0

    required_cols = {"nickname"}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"fluors CSV is missing required columns: {missing}")

    sql = text(
        """
        INSERT INTO public.fluors (
          nickname,
          display_name,
          excitation_nm,
          emission_nm
        )
        VALUES (
          :nickname,
          :display_name,
          :excitation_nm,
          :emission_nm
        )
        """
    )

    with engine.begin() as cx:
        for _, row in df.iterrows():
            nickname = str(row["nickname"]).strip()
            if not nickname:
                continue

            excitation = (
                int(row["excitation_nm"])
                if "excitation_nm" in row and pd.notna(row["excitation_nm"])
                else None
            )
            emission = (
                int(row["emission_nm"])
                if "emission_nm" in row and pd.notna(row["emission_nm"])
                else None
            )

            params = {
                "nickname": nickname,
                "display_name": nickname,  # for now, nickname doubles as display_name
                "excitation_nm": excitation,
                "emission_nm": emission,
            }
            cx.execute(sql, params)
            inserted += 1

    return inserted, updated


def upsert_tags(engine: Engine, df: pd.DataFrame) -> Tuple[int, int]:
    """
    v11: upsert tags using nickname/display_name.
    Expected CSV columns: nickname, localization?, note?.
    """
    inserted = 0
    updated = 0

    required_cols = {"nickname"}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"tags file is missing required columns: {missing}")

    sql = text(
        """
        INSERT INTO public.tags (
          nickname,
          display_name,
          localization,
          notes
        )
        VALUES (
          :nickname,
          :display_name,
          :localization,
          :notes
        )
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
                "nickname": nickname,
                "display_name": nickname,  # nickname doubles as display_name
                "localization": localization,
                "notes": note,
            }
            cx.execute(sql, params)
            inserted += 1

    return inserted, updated


def _build_fluor_lookup(engine: Engine) -> Dict[str, str]:
    """
    Build a mapping from CSV fluor_code → fluors.id (as text),
    using fluors.nickname/display_name.
    """
    sql = text(
        """
        SELECT
          id::text AS fluor_id,
          COALESCE(nickname, display_name, code) AS fluor_label
        FROM public.fluors
        """
    )
    with engine.begin() as cx:
        df = pd.read_sql(sql, cx)

    lookup: Dict[str, str] = {}
    for _, row in df.iterrows():
        fid = str(row["fluor_id"]).strip()
        label = str(row["fluor_label"]).strip()
        if not fid or not label:
            continue
        lookup[label] = fid
        lookup[label.lower()] = fid

    return lookup


def _build_tag_lookup(engine: Engine) -> Dict[str, str]:
    """
    Build a mapping from CSV tag_code → tags.id (as text),
    using tags.nickname/display_name.
    """
    sql = text(
        """
        SELECT
          id::text AS tag_id,
          COALESCE(nickname, display_name, code) AS tag_label
        FROM public.tags
        """
    )
    with engine.begin() as cx:
        df = pd.read_sql(sql, cx)

    lookup: Dict[str, str] = {}
    for _, row in df.iterrows():
        tid = str(row["tag_id"]).strip()
        label = str(row["tag_label"]).strip()
        if not tid or not label:
            continue
        lookup[label] = tid
        lookup[label.lower()] = tid

    return lookup


def upsert_fusions(engine: Engine, df: pd.DataFrame) -> Tuple[int, int]:
    """
    v11: upsert fusions.
    Expected CSV columns: fusion_code, fluor_code, tag_code, tag_pos?, description?.
    """
    inserted = 0
    updated = 0

    required_cols = {"fusion_code", "fluor_code", "tag_code"}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"fusions CSV is missing required columns: {missing}")

    fluor_lookup = _build_fluor_lookup(engine)
    tag_lookup = _build_tag_lookup(engine)

    sql = text(
        """
        INSERT INTO public.fusions (
          fluor_id,
          tag_id,
          tag_pos,
          created_at,
          nickname,
          display_name
        )
        VALUES (
          :fluor_id,
          :tag_id,
          :tag_pos,
          now(),
          :nickname,
          :display_name
        )
        """
    )

    def _norm_key(s: str) -> str:
        return (s or "").strip().lower()

    with engine.begin() as cx:
        for _, row in df.iterrows():
            fusion_code = str(row["fusion_code"]).strip()
            fluor_code = str(row["fluor_code"]).strip() if pd.notna(row["fluor_code"]) else ""
            tag_code = str(row["tag_code"]).strip() if pd.notna(row["tag_code"]) else ""
            tag_pos = (
                str(row["tag_pos"]).strip()
                if "tag_pos" in df.columns and pd.notna(row["tag_pos"])
                else None
            )
            description = (
                str(row["description"]).strip()
                if "description" in df.columns and pd.notna(row["description"])
                else None
            )

            if not fusion_code or not fluor_code:
                continue

            fkey = _norm_key(fluor_code)
            fluor_id = fluor_lookup.get(fkey)
            if fluor_id is None:
                print(f"[WARN] fusion {fusion_code}: fluor_code '{fluor_code}' not found; skipping")
                continue

            tkey = _norm_key(tag_code) if tag_code else ""
            tag_id = tag_lookup.get(tkey) if tkey else None

            cx.execute(
                sql,
                {
                    "fluor_id": fluor_id,
                    "tag_id": tag_id,
                    "tag_pos": tag_pos,
                    "nickname": fusion_code,
                    "display_name": fusion_code,
                },
            )
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
