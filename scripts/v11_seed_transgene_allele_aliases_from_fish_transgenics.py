#!/usr/bin/env python3
from __future__ import annotations

import os
import re
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

REPO = Path(__file__).resolve().parents[1]
CSV = REPO / "seed_kits" / "2025-11-15-121231-autoload" / "fish_transgenics.csv"

BASE_RE = re.compile(r"^([a-z]+)0*([0-9]+)$", re.I)

def canon_base(raw: str) -> str:
    s = (raw or "").strip().lower()
    if not s:
        return ""
    m = BASE_RE.match(s.replace("-", ""))
    if not m:
        return s
    p = m.group(1).lower()
    n = int(m.group(2))
    if p == "pswin":
        return f"pswin-{n}"
    if p == "pdqm":
        return f"pdqm-{n}"
    if p == "mgco":
        return f"mgco-{n}"
    if p == "pjwl":
        return f"pjwl-{n}"
    if p == "pmnm":
        return f"pmnm-{n}"
    return f"{p}-{n}"

def is_numeric_token(x: str) -> bool:
    t = (x or "").strip()
    return t.isdigit() or (t.endswith(".0") and t[:-2].isdigit())

def main() -> None:
    db_url = os.environ.get("DB_URL")
    if not db_url:
        raise SystemExit("[STOP] DB_URL must be set")
    if not CSV.exists():
        raise SystemExit(f"[STOP] missing fish_transgenics.csv: {CSV}")

    df = pd.read_csv(CSV, low_memory=False)
    df.columns = [str(c).strip() for c in df.columns]

    need = {"transgene_base_code", "allele_nickname"}
    miss = sorted(list(need - set(df.columns)))
    if miss:
        raise SystemExit(f"[STOP] fish_transgenics.csv missing columns: {miss}")

    df["base"] = df["transgene_base_code"].astype(str).map(canon_base)
    df["tok"] = df["allele_nickname"].astype(str).str.strip()

    df = df[(df["base"] != "") & (df["tok"] != "")].copy()
    df = df[~df["tok"].map(is_numeric_token)].copy()
    df = df.drop_duplicates(subset=["base", "tok"])

    if df.empty:
        print("[OK] no non-numeric allele_nickname tokens found in fish_transgenics.csv")
        return

    eng = create_engine(db_url)

    sql_one = text("""
        SELECT count(*)::int
        FROM public.transgene_alleles
        WHERE lower(transgene_base_code)=:base
          AND allele_number=1;
    """)

    sql_upd = text("""
        UPDATE public.transgene_alleles
        SET nickname = :tok
        WHERE lower(transgene_base_code)=:base
          AND allele_number=1
          AND coalesce(btrim(nickname),'') <> :tok;
    """)

    updated = 0
    skipped_missing = 0
    with eng.begin() as cx:
        for r in df.itertuples(index=False):
            base = str(r.base).strip().lower()
            tok = str(r.tok).strip()
            n = cx.execute(sql_one, {"base": base}).scalar()
            n = int(n or 0)
            if n != 1:
                skipped_missing += 1
                continue
            res = cx.execute(sql_upd, {"base": base, "tok": tok})
            updated += int(res.rowcount or 0)

    print(f"[OK] transgene_alleles nickname updates={updated} skipped_missing_or_ambiguous={skipped_missing}")

if __name__ == "__main__":
    main()
