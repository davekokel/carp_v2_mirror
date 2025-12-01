#!/usr/bin/env python3
from __future__ import annotations
import argparse, os
from pathlib import Path
import pandas as pd
import os
from sqlalchemy import create_engine, text

def get_engine():
    url = os.environ.get("DB_URL")
    if not url:
        raise SystemExit("DB_URL is not set")
    return create_engine(url)

def norm(x):
    if x is None:
        return ""
    return str(x).strip()

def load_construct_normalized(cx):
    df = pd.read_sql(
        text(
            """
            SELECT
              c.id::text        AS construct_id,
              c.construct_code  AS construct_code,
              c.base_code       AS base_code,
              vc.code_normalized,
              vc.alias
            FROM public.constructs c
            LEFT JOIN public.v_construct_codes_normalized vc
              ON vc.construct_id = c.id
            """
        ),
        cx,
    )
    lut = {}
    for _, r in df.iterrows():
        canon = norm(r["base_code"]) or norm(r["construct_code"])
        if not canon:
            continue
        keys = set()
        for k in [r["construct_code"], r["base_code"], r["code_normalized"], r["alias"]]:
            k = norm(k)
            if not k:
                continue
            keys.add(k)
            keys.add(k.lower())
            k_ns = k.replace(" ", "").replace("-", "")
            if k_ns:
                keys.add(k_ns)
        for k in keys:
            lut[k] = canon
    return lut

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--fish-xlsx", required=True)
    args = p.parse_args()
    path = Path(args.fish_xlsx)
    if not path.exists():
        raise SystemExit(f"[v10_load_fish_lines] fish.xlsx not found: {path}")
    df = pd.read_excel(path)

    # v11 autoload compatibility: derive expected columns from actual sheet columns
    if "construct_base_code" not in df.columns and "transgene_base_code" in df.columns:
        df["construct_base_code"] = df["transgene_base_code"]
    if "stage_key" not in df.columns and "line_building_stage" in df.columns:
        df["stage_key"] = df["line_building_stage"]

    if "construct_base_code" not in df.columns:
        raise SystemExit("[v10_load_fish_lines] missing column 'construct_base_code' in fish.xlsx")
    if "stage_key" not in df.columns:
        raise SystemExit("[v10_load_fish_lines] missing column 'stage_key' in fish.xlsx")
    if "genetic_background" not in df.columns:
        raise SystemExit("[v10_load_fish_lines] missing column 'genetic_background' in fish.xlsx")
    if "nickname" not in df.columns:
        raise SystemExit("[v10_load_fish_lines] missing column 'nickname' in fish.xlsx")

    df = df.copy()
    df["construct_base_code"] = df["construct_base_code"].map(lambda x: norm(x))
    df["stage_key"] = df["stage_key"].map(lambda x: norm(x).lower())
    df["genetic_background"] = df["genetic_background"].map(norm)
    df["nickname"] = df["nickname"].map(norm)

    df = df[df["construct_base_code"] != ""].copy()
    df = df[df["stage_key"].isin(["p0", "f1", "f2", "injections", "injection", "founder", "stable"])]

    if df.empty:
        raise SystemExit("[v10_load_fish_lines] no usable rows after filtering stage_key and construct_base_code")

    engine = get_engine()
    unknown = set()
    with engine.begin() as cx:
        lut = load_construct_normalized(cx)
        df["canon_code"] = ""
        for idx, r in df.iterrows():
            key = norm(r["construct_base_code"])
            if not key:
                continue
            kset = {key, key.lower(), key.replace(" ", ""), key.replace(" ", "").lower(), key.replace("-", ""), key.replace("-", "").lower()}
            canon = None
            for kk in kset:
                if kk in lut:
                    canon = lut[kk]
                    break
            if not canon:
                unknown.add(key)
            else:
                df.at[idx, "canon_code"] = canon
        if unknown:
            uniq = sorted(unknown)
            msg = "[v10_load_fish_lines] WARN: unknown construct_base_code/alias values in fish.xlsx (these rows will be skipped): " + ", ".join(uniq)
            print(msg)
        df = df[df["canon_code"] != ""].copy()

        if df.empty:
            raise SystemExit("[v10_load_fish_lines] all fish rows had unresolvable construct_base_code; fix fish.xlsx or constructs_plasmid.csv")

        lines = {}
        for _, r in df.iterrows():
            canon = r["canon_code"]
            bg = r["genetic_background"]
            nick = r["nickname"]
            key = (canon, bg, nick)
            if key not in lines:
                res = cx.execute(
                    text(
                        """
                        INSERT INTO public.fish_lines (
                          id,
                          line_code,
                          construct_code,
                          genetic_background,
                          nickname,
                          created_at
                        )
                        VALUES (
                          gen_random_uuid(),
                          'LINE-' || substr(gen_random_uuid()::text, 1, 8),
                          :construct_code,
                          :bg,
                          :nickname,
                          now()
                        )
                        RETURNING id, line_code
                        """
                    ),
                    {"construct_code": canon, "bg": bg or None, "nickname": nick or None},
                ).fetchone()
                lines[key] = {"line_id": res.id, "line_code": res.line_code}
        for _, r in df.iterrows():
            canon = r["canon_code"]
            bg = r["genetic_background"]
            nick = r["nickname"]
            key = (canon, bg, nick)
            if key not in lines:
                continue
            line_id = lines[key]["line_id"]
            line_code = lines[key]["line_code"]
            stage = r["stage_key"] or None
            birthday = r.get("birthday")
            fc = f"{line_code}-{stage or 'X'}-{_+1:03d}"
            cx.execute(
                text(
                    """
                    INSERT INTO public.fish_instances_v10 (
                      id,
                      line_id,
                      line_instance_code,
                      fish_code,
                      birthday,
                      genotype_v11_id,
                      created_at
                    )
                    VALUES (
                      gen_random_uuid(),
                      :line_id,
                      :lic,
                      :fish_code,
                      :birthday,
                      NULL,
                      now()
                    )
                    """
                ),
                {"line_id": line_id, "lic": fc, "fish_code": fc, "birthday": birthday},
            )

    print(f"[v10_load_fish_lines] loaded {len(df)} seed rows into fish_lines and fish_instances_v10")

if __name__ == "__main__":
    main()
