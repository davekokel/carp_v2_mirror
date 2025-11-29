from __future__ import annotations

import argparse
import sys
import pathlib
import pandas as pd
from sqlalchemy import text

# ───────── repo bootstrap (same pattern as other loaders) ─────────
ROOT = pathlib.Path(__file__).resolve().parents[1]  # scripts/ → repo root
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from carp_app.ui.lib.app_ctx import get_engine


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True, help="CSV with alias,line_nickname")
    args = ap.parse_args()

    df = pd.read_csv(args.csv)
    df["alias"] = df["alias"].astype(str).str.strip()
    df["line_nickname"] = df["line_nickname"].astype(str).str.strip()

    eng = get_engine()
    inserted = 0
    skipped_no_line = 0
    skipped_existing = 0

    with eng.begin() as cx:
        # preload nickname → line_id
        df_lines = pd.read_sql(
            text("SELECT id::text AS line_id, nickname FROM public.fish_lines"),
            cx,
        )
        nick_to_line = {
            str(r.nickname).strip(): str(r.line_id).strip()
            for _, r in df_lines.iterrows()
        }

        for _, r in df.iterrows():
            alias = str(r["alias"]).strip()
            nick = str(r["line_nickname"]).strip()

            if not alias or not nick:
                continue

            line_id = nick_to_line.get(nick)
            if not line_id:
                print(f"[WARN] nickname not found in fish_lines: '{nick}' → skip '{alias}'")
                skipped_no_line += 1
                continue

            # avoid duplicates
            exists = pd.read_sql(
                text("""
                    SELECT 1
                    FROM public.fish_line_aliases
                    WHERE alias = :alias AND line_id = :lid
                    LIMIT 1;
                """),
                cx,
                params={"alias": alias, "lid": line_id},
            )
            if not exists.empty:
                skipped_existing += 1
                continue

            cx.execute(
                text("""
                    INSERT INTO public.fish_line_aliases (id, alias, line_id, created_at)
                    VALUES (gen_random_uuid(), :alias, :lid, now());
                """),
                {"alias": alias, "lid": line_id},
            )
            inserted += 1
            print(f"[OK] {alias} → {nick}")

    print(f"[DONE] inserted={inserted}  skipped_no_line={skipped_no_line}  skipped_existing={skipped_existing}")


if __name__ == "__main__":
    main()
