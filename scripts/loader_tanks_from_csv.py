from __future__ import annotations
import os
from pathlib import Path
from typing import Optional

import pandas as pd
from sqlalchemy import create_engine, text


BASE = Path(__file__).resolve().parents[1]
DEFAULT_CSV = BASE / "seed_kits" / "2025-11-15-121231-autoload" / "tanks.csv"


def main(csv_path: Optional[str] = None, import_batch_id: Optional[str] = None) -> None:
    db_url = os.environ.get("DB_URL")
    if not db_url:
        raise SystemExit("DB_URL is not set")

    path = Path(csv_path) if csv_path else DEFAULT_CSV
    if not path.exists():
        raise SystemExit(f"CSV not found: {path}")

    df = pd.read_csv(path)

    required_cols = {"tank_code", "fish_code"}
    missing = required_cols - set(df.columns)
    if missing:
        raise SystemExit(f"CSV is missing required columns: {sorted(missing)}")

    if import_batch_id is None:
        if "import_batch_id" in df.columns and df["import_batch_id"].notna().any():
            import_batch_id = str(df["import_batch_id"].dropna().iloc[0])
        else:
            import_batch_id = path.stem

    engine = create_engine(db_url)

    with engine.begin() as cx:
        fish_codes = df["fish_code"].dropna().unique().tolist()
        rows = cx.execute(
            text(
                """
                SELECT fish_code, id
                FROM public.fish_instance
                WHERE fish_code = ANY(:codes)
                """
            ),
            {"codes": fish_codes},
        ).mappings().all()
        code_to_id = {row["fish_code"]: row["id"] for row in rows}

        print(f"[INFO] Resolved {len(code_to_id)} fish_code(s) to fish_id(s).")
        unknown = sorted(set(fish_codes) - set(code_to_id))
        if unknown:
            print(f"[WARN] {len(unknown)} fish_code(s) not found in fish_instance; skipping those rows.")
            for code in unknown[:20]:
                print(f"  - {code}")

        cx.execute(
            text(
                """
                ALTER TABLE public.tanks
                ADD COLUMN IF NOT EXISTS import_batch_id text
                """
            )
        )

        cx.execute(
            text(
                """
                DELETE FROM public.tanks
                WHERE import_batch_id = :batch
                """
            ),
            {"batch": import_batch_id},
        )
        print(f"[INFO] Deleted existing tanks for import_batch_id={import_batch_id!r}.")

        inserted = 0
        for _, row in df.iterrows():
            fish_code = row.get("fish_code")
            fish_id = code_to_id.get(fish_code)
            if fish_id is None:
                continue

            payload = {
                "tank_code": row.get("tank_code"),
                "fish_id": fish_id,
                "status": row.get("status") or "active",
                "location": row.get("location"),
                "volume_l": row.get("volume_l"),
                "notes": row.get("tank_notes") or "",
                "import_batch_id": import_batch_id,
            }

            cx.execute(
                text(
                    """
                    INSERT INTO public.tanks (
                        tank_code,
                        fish_id,
                        status,
                        location,
                        volume_l,
                        notes,
                        import_batch_id
                    )
                    VALUES (
                        :tank_code,
                        :fish_id,
                        :status,
                        :location,
                        :volume_l,
                        :notes,
                        :import_batch_id
                    )
                    """
                ),
                payload,
            )
            inserted += 1

        print(f"[OK] Inserted {inserted} tank(s) for batch={import_batch_id!r}.")


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--csv", type=str, default=None, help="Path to tanks CSV")
    p.add_argument("--batch", type=str, default=None, help="Override import_batch_id label")
    args = p.parse_args()
    main(csv_path=args.csv, import_batch_id=args.batch)
