#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


def _norm(s: str | None) -> str:
    if s is None:
        return ""
    t = str(s).strip()
    return t


def get_engine(db_url: str | None) -> Engine:
    url = db_url or os.environ.get("DB_URL")
    if not url:
        raise SystemExit("DB_URL must be provided via --db-url or env DB_URL")
    print(f"DB_URL={url}")
    return create_engine(url)


def _ensure_injection_treatment_for_base(engine: Engine, base_code: str) -> str:
    bc = _norm(base_code)
    if not bc:
        raise ValueError("Base code is required to create an injection treatment")

    tcode = f"INJ-{bc}"

    with engine.begin() as cx:
        row = cx.execute(
            text(
                """
                SELECT id::text AS treatment_id
                FROM public.treatments
                WHERE treat_code = :tcode
                LIMIT 1;
                """
            ),
            {"tcode": tcode},
        ).fetchone()
        if row is not None:
            return row[0]

        tname = f"Injection of {bc}"

        new_row = cx.execute(
            text(
                """
                INSERT INTO public.treatments (
                  id,
                  treat_code,
                  kind_code,
                  treat_text,
                  notes,
                  created_at,
                  source_system,
                  import_batch_id,
                  nickname,
                  display_name,
                  treatment_type
                )
                VALUES (
                  gen_random_uuid(),
                  :tcode,
                  'injection',
                  :tname,
                  NULL,
                  now(),
                  'fish_v11_treatments_csv',
                  'fish_v11_treatments_csv',
                  :nickname,
                  :dname,
                  'injection'
                )
                RETURNING id::text AS treatment_id;
                """
            ),
            {"tcode": tcode, "tname": tname, "nickname": tcode, "dname": tname},
        ).fetchone()

    return new_row[0]


def load_fish_treatments_from_csv(csv_path: Path, engine: Engine) -> Dict[str, int]:
    df = pd.read_csv(csv_path)
    df.columns = [c.strip() for c in df.columns]

    for col in ("fish_code", "treatment_code"):
        if col not in df.columns:
            raise SystemExit(f"CSV must have column {col!r}")

    if "notes" not in df.columns:
        df["notes"] = ""

    df["fish_code"] = df["fish_code"].astype("string")
    df["treatment_code"] = df["treatment_code"].astype("string")
    df["notes"] = df["notes"].astype("string")

    # Resolve fish_code → fish_instance_id
    with engine.begin() as cx:
        fish_df = pd.read_sql(
            text(
                """
                SELECT fish_code, id::text AS fish_instance_id
                FROM public.fish_instances_v10;
                """
            ),
            cx,
        )
    fish_map: Dict[str, str] = {
        (_norm(r["fish_code"])): _norm(r["fish_instance_id"])
        for _, r in fish_df.iterrows()
        if _norm(r["fish_code"])
    }

    n_links = 0
    n_missing_fish = 0
    n_missing_treatments = 0
    n_created_inj = 0

    with engine.begin() as cx:
        for _, row in df.iterrows():
            fcode = _norm(row["fish_code"])
            tcode = _norm(row["treatment_code"])
            notes = _norm(row.get("notes"))

            if not fcode or not tcode:
                continue

            fid = fish_map.get(fcode)
            if not fid:
                print(f"[WARN] fish_code {fcode!r} not found; skipping")
                n_missing_fish += 1
                continue

            # Resolve treatment_id, with optional injection auto-create
            tret = cx.execute(
                text(
                    """
                    SELECT id::text AS treatment_id
                    FROM public.treatments
                    WHERE treat_code = :tcode
                    LIMIT 1;
                    """
                ),
                {"tcode": tcode},
            ).fetchone()

            if tret is None and tcode.startswith("INJ-") and len(tcode) > 4:
                base_code = tcode[4:]
                # Commit current transaction and create via helper using engine
                cx.commit()
                tid = _ensure_injection_treatment_for_base(engine, base_code)
                n_created_inj += 1
                cx = engine.begin()
            elif tret is None:
                print(f"[WARN] treatment_code {tcode!r} not found; skipping")
                n_missing_treatments += 1
                continue
            else:
                tid = tret[0]

            cx.execute(
                text(
                    """
                    INSERT INTO public.join_fish_treatments (
                      id,
                      fish_instance_id,
                      treatment_id,
                      created_at,
                      notes
                    )
                    VALUES (
                      gen_random_uuid(),
                      (:fid)::uuid,
                      (:tid)::uuid,
                      now(),
                      :notes
                    )
                    ON CONFLICT (fish_instance_id, treatment_id) DO NOTHING;
                    """
                ),
                {"fid": fid, "tid": tid, "notes": notes},
            )
            n_links += 1

    return {
        "n_links": n_links,
        "n_missing_fish": n_missing_fish,
        "n_missing_treatments": n_missing_treatments,
        "n_created_injection_treatments": n_created_inj,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="v11: load fish→treatment links from CSV into join_fish_treatments"
    )
    parser.add_argument(
        "--csv",
        required=True,
        help="Path to fish_v11_treatments.csv",
    )
    parser.add_argument(
        "--db-url",
        help="Override DB_URL",
    )
    args = parser.parse_args()

    path = Path(args.csv)
    if not path.exists():
        raise SystemExit(f"Treatments CSV not found: {path}")

    engine = get_engine(args.db_url)
    print(f"[INFO] Reading treatments CSV from: {path}")
    summary = load_fish_treatments_from_csv(path, engine)

    print(
        f"[OK] Inserted {summary['n_links']} join_fish_treatments row(s). "
        f"missing fish={summary['n_missing_fish']}, "
        f"missing treatments={summary['n_missing_treatments']}, "
        f"created injection treatments={summary['n_created_injection_treatments']}"
    )


if __name__ == "__main__":
    main()
