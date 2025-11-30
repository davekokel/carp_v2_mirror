#!/usr/bin/env python3
from __future__ import annotations
import argparse, os
from pathlib import Path
import pandas as pd
from sqlalchemy import create_engine, text

def get_engine():
    return create_engine(os.environ["DB_URL"])

def norm(x):
    if x is None:
        return ""
    return str(x).strip()

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--fish-xlsx", required=True)
    args = p.parse_args()

    df = pd.read_excel(Path(args.fish_xlsx))

    df["transgene_base_code"] = df["transgene_base_code"].astype(str).str.strip()
    df["allele_nickname"] = df["allele_nickname"].astype(str).str.strip()
    df["genetic_background"] = df["genetic_background"].astype(str).str.strip()
    df["nickname"] = df["nickname"].astype(str).str.strip()
    df["description"] = df["description"].astype(str).str.strip()

    df = df[df["transgene_base_code"].notna()]

    with get_engine().begin() as cx:
        lines = {}
        for _, r in df.iterrows():
            key = (
                norm(r.transgene_base_code),
                norm(r.allele_nickname),
                norm(r.genetic_background),
                norm(r.nickname)
            )
            if key not in lines:
                row = cx.execute(
                    text("""
                        INSERT INTO public.fish_lines
                          (line_code, transgene_base_code, allele_nickname, genetic_background, nickname)
                        VALUES
                          (
                            'LINE-'||substr(gen_random_uuid()::text,1,8),
                            :base,
                            :allele,
                            :bg,
                            :nn
                          )
                        RETURNING id, line_code
                    """),
                    {
                        "base": key[0],
                        "allele": key[1],
                        "bg": key[2],
                        "nn": key[3]
                    }
                ).fetchone()
                lines[key] = {"line_id": row.id}

        for _, r in df.iterrows():
            key = (
                norm(r.transgene_base_code),
                norm(r.allele_nickname),
                norm(r.genetic_background),
                norm(r.nickname)
            )
            if key not in lines:
                continue

            cx.execute(
                text("""
                    INSERT INTO public.fish_instances_v10
                      (line_instance_code, line_id, fish_code, birthday, notes)
                    VALUES
                      (
                        'LINEINST-'||substr(gen_random_uuid()::text,1,8),
                        :line_id,
                        'FISH-'||substr(gen_random_uuid()::text,1,8),
                        :birthday,
                        :notes
                      )
                """),
                {
                    "line_id": lines[key]["line_id"],
                    "birthday": r.get("birthday"),
                    "notes": r.get("description")
                }
            )

if __name__ == "__main__":
    main()
