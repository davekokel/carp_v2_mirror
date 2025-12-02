#!/usr/bin/env python3
from __future__ import annotations
import os
import pandas as pd
from sqlalchemy import create_engine, text

def engine():
    url = os.environ.get("DB_URL")
    if not url:
        raise SystemExit("DB_URL not set")
    return create_engine(url)

def main():
    eng = engine()

    with eng.begin() as cx:
        df_lines = pd.read_sql(
            text("SELECT nickname FROM public.fish_lines"),
            cx,
        )

        # all distinct, non-empty nicknames
        nicks = sorted({str(x).strip() for x in df_lines["nickname"].dropna() if str(x).strip()})

        # loader requires line_nickname and alias columns
        out = []
        for nick in nicks:
            out.append(
                {
                    "line_nickname": nick,
                    "alias": nick,
                }
            )

        df_out = pd.DataFrame(out)
        path = "seed_kits/legacy_wrangling_v2/working/fish_aliases_v11.csv"
        df_out.to_csv(path, index=False)

        print(f"[OK] wrote {len(df_out)} alias rows → {path}")

if __name__ == "__main__":
    main()
