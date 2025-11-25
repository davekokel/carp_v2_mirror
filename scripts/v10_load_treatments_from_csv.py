from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Optional, Dict

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


def get_engine(db_url: Optional[str]) -> Engine:
    url = db_url or os.environ.get("DB_URL")
    if not url:
        raise SystemExit("DB_URL must be provided via --db-url or env DB_URL")
    print(f"DB_URL={url}")
    return create_engine(url)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="v10: load treatments + mixes + ingredients from treatments CSV"
    )
    parser.add_argument(
        "--csv",
        required=True,
        help="Path to treatments CSV",
    )
    parser.add_argument(
        "--db-url",
        help="Override DB_URL",
    )
    args = parser.parse_args()

    path = Path(args.csv)
    if not path.exists():
        raise SystemExit(f"treatments CSV not found: {path}")

    df = pd.read_csv(path)
    print(f"[v10_load_treatments] read {len(df)} row(s) from {path}")

    required = [
        "treatment_code",
        "treatment_name",
        "mix_code",
        "ingredient_type",
        "ingredient_code",
        "concentration",
    ]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise SystemExit(f"treatments CSV missing required columns: {missing}; found {list(df.columns)}")

    df = df.copy()
    for col in required:
        df[col] = df[col].astype(str).fillna("").str.strip()

    engine = get_engine(args.db_url)

    insert_treatment = text(
        """
        INSERT INTO public.treatments (
          treat_code,
          kind_code,
          treat_text,
          notes,
          created_at
        )
        VALUES (
          :code,
          'injection',
          :name,
          NULL,
          now()
        )
        ON CONFLICT (treat_code) DO UPDATE SET
          treat_text = EXCLUDED.treat_text
        RETURNING id::text AS treatment_id
        """
    )

    insert_mix = text(
        """
        INSERT INTO public.treatment_mixes (
          treatment_id,
          mix_code,
          notes,
          created_at
        )
        VALUES (
          :treatment_id,
          :mix_code,
          NULL,
          now()
        )
        RETURNING id::text AS mix_id
        """
    )

    insert_ingredient = text(
        """
        INSERT INTO public.mix_ingredients (
          mix_id,
          ingredient_type,
          ingredient_id,
          concentration,
          notes,
          created_at
        )
        VALUES (
          :mix_id,
          :itype,
          :iid,
          :conc,
          NULL,
          now()
        )
        """
    )

    with engine.begin() as cx:
        df_constructs = pd.read_sql(
            text("SELECT id::text AS construct_id, construct_code FROM public.constructs"),
            cx,
        )
        df_dyes = pd.read_sql(
            text("SELECT id::text AS dye_id, dye_base_code FROM public.dyes"),
            cx,
        )

    code_to_cid: Dict[str, str] = {
        row["construct_code"].strip(): row["construct_id"]
        for _, row in df_constructs.iterrows()
    }
    dye_to_id: Dict[str, str] = {
        row["dye_base_code"].strip(): row["dye_id"]
        for _, row in df_dyes.iterrows()
    }

    inserted_treatments = 0
    inserted_mixes = 0
    inserted_ingredients = 0
    skipped_ingredients = 0

    with engine.begin() as cx:
        for (t_code, mix_code), sub in df.groupby(["treatment_code", "mix_code"]):
            t_name = sub["treatment_name"].iloc[0]

            res_t = cx.execute(
                insert_treatment,
                {"code": t_code, "name": t_name},
            ).fetchone()
            treatment_id = res_t._mapping["treatment_id"]
            inserted_treatments += 1

            res_m = cx.execute(
                insert_mix,
                {"treatment_id": treatment_id, "mix_code": mix_code},
            ).fetchone()
            mix_id = res_m._mapping["mix_id"]
            inserted_mixes += 1

            for _, row in sub.iterrows():
                itype = row["ingredient_type"].lower()
                icode = row["ingredient_code"]
                conc  = row["concentration"] or None

                iid: Optional[str] = None
                if itype == "construct":
                    iid = code_to_cid.get(icode)
                elif itype == "dye":
                    iid = dye_to_id.get(icode)

                if iid is None:
                    print(f"[v10_load_treatments] SKIP ingredient: type={itype} code={icode} (not found)")
                    skipped_ingredients += 1
                    continue

                cx.execute(
                    insert_ingredient,
                    {
                        "mix_id": mix_id,
                        "itype": itype,
                        "iid": iid,
                        "conc": conc,
                    },
                )
                inserted_ingredients += 1

    print(f"[v10_load_treatments] inserted/updated ~{inserted_treatments} treatments")
    print(f"[v10_load_treatments] inserted {inserted_mixes} mixes")
    print(f"[v10_load_treatments] inserted {inserted_ingredients} ingredients; skipped {skipped_ingredients}")
