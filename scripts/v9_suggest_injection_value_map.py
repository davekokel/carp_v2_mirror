#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import re
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

NULLISH = {"", "nan", "none", "na", "n/a", "<na>"}

def get_engine(db_url: str | None) -> Engine:
    url = db_url or os.environ.get("DB_URL")
    if not url:
        raise SystemExit("DB_URL must be set (env DB_URL or --db-url)")
    return create_engine(url)

def norm_cell(x) -> str:
    if x is None:
        return ""
    s = str(x).strip()
    return "" if s.lower() in NULLISH else s

def normalize_token(s: str) -> str:
    s = s.strip()
    s = re.sub(r"\(.*\)$", "", s).strip()
    s = re.sub(r"[^A-Za-z0-9]+", "-", s).strip("-")
    m = re.match(r"^([A-Za-z]+)-?(0*)(\d+)$", s)
    if m:
        return f"{m.group(1).lower()}-{int(m.group(3))}"
    return s.lower()

def extract_candidate_tokens(raw_value: str) -> List[str]:
    s = raw_value.strip()
    s = s.replace(";", ",")
    parts = [p.strip() for p in s.split(",") if p.strip()]
    toks: List[str] = []
    for p in parts:
        p2 = p.strip()
        if not p2:
            continue
        base = p2.split("(")[0].strip()
        if base:
            toks.append(base)
        toks.append(p2)
    out: List[str] = []
    seen = set()
    for t in toks:
        nt = normalize_token(t)
        if nt and nt not in seen:
            seen.add(nt)
            out.append(nt)
    return out

def load_construct_lookup(engine: Engine) -> Dict[str, List[Tuple[str, str]]]:
    sql = text(
        """
        SELECT
          c.base_code,
          c.construct_code,
          a.alias
        FROM public.constructs c
        LEFT JOIN public.construct_aliases a
          ON a.construct_id = c.id
        """
    )
    with engine.begin() as cx:
        df = pd.read_sql(sql, cx)

    lut: Dict[str, List[Tuple[str, str]]] = {}
    def add(key: str, base_code: str, source: str) -> None:
        k = normalize_token(key)
        if not k:
            return
        lut.setdefault(k, []).append((base_code, source))

    for _, r in df.iterrows():
        base_code = norm_cell(r.get("base_code"))
        construct_code = norm_cell(r.get("construct_code"))
        alias = norm_cell(r.get("alias"))

        if base_code:
            add(base_code, base_code, "base_code")
        if construct_code and base_code:
            add(construct_code, base_code, "construct_code")
        if alias and base_code:
            add(alias, base_code, "alias")

    return lut

def rank_candidates(hits: List[Tuple[str, str]]) -> List[str]:
    seen = {}
    for base_code, src in hits:
        seen.setdefault(base_code, set()).add(src)

    def score(srcs: set) -> Tuple[int, int]:
        return (
            1 if "base_code" in srcs else 0,
            1 if "construct_code" in srcs else 0,
        )

    ranked = sorted(seen.items(), key=lambda kv: (score(kv[1]), kv[0]))
    ranked = list(reversed(ranked))
    return [bc for bc, _srcs in ranked]

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in-csv", required=True)
    ap.add_argument("--out-csv", required=True)
    ap.add_argument("--db-url")
    args = ap.parse_args()

    inp = Path(args.in_csv)
    if not inp.exists():
        raise SystemExit(f"Input CSV not found: {inp}")

    df = pd.read_csv(inp, low_memory=False)
    need = {"channel", "raw_value", "n_rows"}
    missing = sorted(list(need - set(df.columns)))
    if missing:
        raise SystemExit(f"[STOP] mapping CSV missing columns: {missing}")

    eng = get_engine(args.db_url)
    lut = load_construct_lookup(eng)

    out_rows = []
    for _, r in df.iterrows():
        channel = norm_cell(r.get("channel"))
        raw_value = norm_cell(r.get("raw_value"))
        n_rows = int(r.get("n_rows") or 0)

        if not channel or channel not in ("rna", "plasmid"):
            raise SystemExit(f"[STOP] bad channel value: {channel!r} for raw_value={raw_value!r}")

        if not raw_value:
            continue

        toks = extract_candidate_tokens(raw_value)
        hits: List[Tuple[str, str]] = []
        for t in toks:
            hits.extend(lut.get(t, []))

        cands = rank_candidates(hits)[:3] if hits else []

        out_rows.append(
            {
                "channel": channel,
                "raw_value": raw_value,
                "n_rows": n_rows,
                "candidate_1": cands[0] if len(cands) > 0 else "",
                "candidate_2": cands[1] if len(cands) > 1 else "",
                "candidate_3": cands[2] if len(cands) > 2 else "",
                "mapped_base_code": "",
                "dismiss_reason": "",
                "notes": "",
            }
        )

    outp = Path(args.out_csv)
    outp.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(out_rows).to_csv(outp, index=False)
    print(f"[OK] wrote {outp} rows={len(out_rows)}")

if __name__ == "__main__":
    main()
