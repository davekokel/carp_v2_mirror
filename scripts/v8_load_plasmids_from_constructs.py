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


def upsert_plasmids(engine: Engine, df: pd.DataFrame) -> Tuple[int, int]:
    inserted = 0
    updated = 0

    required_cols = {"plasmid_code"}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"constructs_plasmid.csv missing required columns: {missing}")

    sql = text(
        """
        INSERT INTO public.plasmids (
          code,
          plasmid_base_code,
          name,
          nickname,
          resistance,
          notes
        )
        VALUES (
          :code,
          :base_code,
          :name,
          :nickname,
          :resistance,
          :notes
        )
        ON CONFLICT (code) DO UPDATE SET
          plasmid_base_code = EXCLUDED.plasmid_base_code,
          name              = EXCLUDED.name,
          nickname          = EXCLUDED.nickname,
          resistance        = EXCLUDED.resistance,
          notes             = EXCLUDED.notes
        """
    )

    with engine.begin() as cx:
        for _, row in df.iterrows():
            raw_code = str(row["plasmid_code"]).strip()
            if not raw_code:
                continue

            base_code = raw_code  # no normalization yet; matches existing transgenes
            name = (
                str(row["plasmid_name"]).strip()
                if "plasmid_name" in df.columns and pd.notna(row["plasmid_name"])
                else None
            )
            nickname = raw_code
            resistance = (
                str(row["resistance"]).strip()
                if "resistance" in df.columns and pd.notna(row["resistance"])
                else None
            )
            notes = (
                str(row["plasmid_notes"]).strip()
                if "plasmid_notes" in df.columns and pd.notna(row["plasmid_notes"])
                else None
            )

            params = {
                "code": base_code,
                "base_code": base_code,
                "name": name,
                "nickname": nickname,
                "resistance": resistance,
                "notes": notes,
            }
            cx.execute(sql, params)
            inserted += 1

    return inserted, updated


def upsert_fusions_and_links(engine: Engine, df: pd.DataFrame) -> Tuple[int, int]:
    inserted_fusions = 0

    required_cols = {"plasmid_code", "fluor_code", "tag_code", "tag_pos"}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(
            f"constructs_plasmid.csv missing required columns for fusions/linking: {missing}"
        )

    plasmid_lookup_sql = text(
        "SELECT id FROM public.plasmids WHERE code = :code"
    )
    fluor_lookup_sql = text(
        "SELECT id FROM public.fluors WHERE lower(fluor_code) = lower(:fluor_code)"
    )
    fluor_alias_lookup_sql = text(
        "SELECT fluor_id FROM public.fluor_aliases WHERE lower(alias) = lower(:alias)"
    )
    tag_lookup_sql = text(
        "SELECT id FROM public.tags WHERE lower(tag_code) = lower(:tag_code)"
    )

    fusion_lookup_sql = text(
        """
        SELECT id
        FROM public.fusions
        WHERE fluor_id = :fluor_id
          AND tag_id   IS NOT DISTINCT FROM :tag_id
        """
    )

    fusion_insert_sql = text(
        """
        INSERT INTO public.fusions (fluor_id, tag_id, tag_pos)
        VALUES (:fluor_id, :tag_id, :tag_pos)
        RETURNING id
        """
    )

    link_sql = text(
        """
        INSERT INTO public.join_plasmid_fusions (plasmid_id, fusion_id)
        VALUES (:plasmid_id, :fusion_id)
        ON CONFLICT DO NOTHING
        """
    )

    with engine.begin() as cx:
        for _, row in df.iterrows():
            plasmid_code = str(row["plasmid_code"]).strip()
            fluor_code = (
                str(row["fluor_code"]).strip()
                if pd.notna(row["fluor_code"])
                else None
            )
            tag_code = (
                str(row["tag_code"]).strip()
                if pd.notna(row["tag_code"])
                else None
            )
            tag_pos = (
                str(row["tag_pos"]).strip()
                if "tag_pos" in df.columns and pd.notna(row["tag_pos"])
                else None
            )

            if not fluor_code:
                continue

            plasmid_id = cx.execute(plasmid_lookup_sql, {"code": plasmid_code}).scalar()
            if plasmid_id is None:
                print(f"[WARN] Plasmid code '{plasmid_code}' not found; skipping fusion for this row")
                continue

            fluor_id = cx.execute(fluor_lookup_sql, {"fluor_code": fluor_code}).scalar()
            if fluor_id is None:
                fluor_id = cx.execute(
                    fluor_alias_lookup_sql, {"alias": fluor_code}
                ).scalar()
                if fluor_id is None:
                    print(
                        f"[WARN] fluor_code '{fluor_code}' not found in public.fluors or fluor_aliases; skipping fusion"
                    )
                    continue

            tag_id = None
            if tag_code:
                tag_id = cx.execute(tag_lookup_sql, {"tag_code": tag_code}).scalar()
                if tag_id is None:
                    print(
                        f"[WARN] tag_code '{tag_code}' not found in public.tags; treating as no tag"
                    )
                    tag_id = None

            fusion_id = cx.execute(
                fusion_lookup_sql,
                {"fluor_id": fluor_id, "tag_id": tag_id},
            ).scalar()

            if fusion_id is None:
                fusion_id = cx.execute(
                    fusion_insert_sql,
                    {"fluor_id": fluor_id, "tag_id": tag_id, "tag_pos": tag_pos},
                ).scalar()
                inserted_fusions += 1

            cx.execute(
                link_sql,
                {"plasmid_id": plasmid_id, "fusion_id": fusion_id},
            )

    return inserted_fusions, 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Load v8 plasmids, fusions, and join_plasmid_fusions from constructs_plasmid.csv"
    )
    parser.add_argument(
        "--constructs-csv",
        required=True,
        help="Path to constructs_plasmid.csv",
    )
    args = parser.parse_args()

    engine = get_engine()

    if not os.path.exists(args.constructs_csv):
        raise FileNotFoundError(f"constructs CSV not found: {args.constructs_csv}")

    df = pd.read_csv(args.constructs_csv)

    ins_plasmids, _ = upsert_plasmids(engine, df)
    print(f"plasmids: handled={ins_plasmids}")

    ins_fusions, _ = upsert_fusions_and_links(engine, df)
    print(f"fusions:  new_inserted={ins_fusions} (via constructs)")


if __name__ == "__main__":
    main()
