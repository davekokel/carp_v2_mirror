from __future__ import annotations

import os, pathlib, sys
from typing import Dict, Tuple

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from carp_app.etl.code_normalization import normalize_base_code

CSV_PATH = ROOT / "seed_kits" / "2025-11-15-121231-autoload" / "plasmid_fusions.csv"


def get_engine() -> Engine:
    db_url = os.getenv("DB_URL")
    if not db_url:
        raise RuntimeError("DB_URL not set")
    return create_engine(db_url)


def load_csv() -> pd.DataFrame:
    df = pd.read_csv(CSV_PATH)
    df["plasmid_code_norm"] = df["plasmid_base_code"].astype(str).map(normalize_base_code)
    df["fluor"] = df["fluor"].astype(str).str.strip()
    df["tag"] = df["tag"].astype(str).str.strip()
    df["tag_pos"] = df["tag_pos"].astype(str).str.strip().replace({"nan": ""})
    return df


def build_fusions_from_csv(engine: Engine, df: pd.DataFrame) -> None:
    fusion_cache: Dict[Tuple[str, str | None, str], str] = {}

    with engine.begin() as cx:
        plasmid_rows = cx.execute(
            text("SELECT id, code FROM public.plasmids")
        ).mappings().all()
        plasmid_map = {str(r["code"]).upper(): str(r["id"]) for r in plasmid_rows}

        fluor_rows = cx.execute(
            text("SELECT id, fluor_code FROM public.fluors")
        ).mappings().all()
        # case-insensitive map
        fluor_map = {str(r["fluor_code"]).lower(): str(r["id"]) for r in fluor_rows}

        tag_rows = cx.execute(
            text("SELECT id, tag_code FROM public.tags")
        ).mappings().all()
        tag_map = {str(r["tag_code"]).lower(): str(r["id"]) for r in tag_rows}

        codes = sorted(df["plasmid_code_norm"].dropna().unique())
        if codes:
            cx.execute(
                text(
                    """
                    DELETE FROM public.join_plasmid_fusions
                    WHERE plasmid_id IN (
                      SELECT id FROM public.plasmids WHERE code = ANY(:codes)
                    )
                    """
                ),
                {"codes": codes},
            )

        for _, row in df.iterrows():
            code_norm = row["plasmid_code_norm"]
            fluor_code = (row["fluor"] or "").strip()
            tag_code = (row["tag"] or "").strip()
            tag_pos = (row["tag_pos"] or "").strip()

            if not code_norm or code_norm not in plasmid_map:
                continue

            fluor_key = fluor_code.lower()
            if fluor_key not in fluor_map:
                continue

            plasmid_id = plasmid_map[code_norm]
            fluor_id = fluor_map[fluor_key]

            tag_id = None
            if tag_code:
                tag_key = tag_code.lower()
                tag_id = tag_map.get(tag_key)

            key = (fluor_id, tag_id, tag_pos)
            fusion_id = fusion_cache.get(key)

            if fusion_id is None:
                row2 = cx.execute(
                    text(
                        """
                        SELECT id
                        FROM public.fusions
                        WHERE fluor_id = :fluor_id
                          AND (
                                (tag_id IS NULL AND :tag_id IS NULL)
                             OR tag_id = :tag_id
                          )
                          AND COALESCE(tag_pos, '') = COALESCE(:tag_pos, '')
                        """
                    ),
                    {
                        "fluor_id": fluor_id,
                        "tag_id": tag_id,
                        "tag_pos": tag_pos or "",
                    },
                ).fetchone()

                if row2:
                    fusion_id = row2[0]
                else:
                    fusion_id = cx.execute(
                        text(
                            """
                            INSERT INTO public.fusions (fluor_id, tag_id, tag_pos)
                            VALUES (:fluor_id, :tag_id, :tag_pos)
                            RETURNING id
                            """
                        ),
                        {
                            "fluor_id": fluor_id,
                            "tag_id": tag_id,
                            "tag_pos": tag_pos or None,
                        },
                    ).scalar()

                fusion_cache[key] = fusion_id

            cx.execute(
                text(
                    """
                    INSERT INTO public.join_plasmid_fusions (plasmid_id, fusion_id)
                    VALUES (:plasmid_id, :fusion_id)
                    ON CONFLICT DO NOTHING
                    """
                ),
                {"plasmid_id": plasmid_id, "fusion_id": fusion_id},
            )


def main() -> None:
    print(f"DB_URL={os.getenv('DB_URL','')}")
    print(f"Using CSV: {CSV_PATH}")
    engine = get_engine()
    df = load_csv()
    build_fusions_from_csv(engine, df)
    print("Reloaded plasmid fusions from CSV.")


if __name__ == "__main__":
    main()
