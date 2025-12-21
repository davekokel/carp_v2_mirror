#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import pandas as pd
from sqlalchemy import create_engine, text

MAP_CSV = "seed_kits/legacy_wrangling_v3/working/exp_treatment_token_map.csv"

RX_MGCO = re.compile(r"\bmgco-0*([0-9]+)\b", re.I)
RX_PDQM = re.compile(r"\bpdqm-0*([0-9]+)\b", re.I)
RX_HC   = re.compile(r"\bhc-0*([0-9]+)\b", re.I)

def main() -> None:
    db_url = os.environ.get("DB_URL")
    if not db_url:
        raise SystemExit("[STOP] DB_URL is not set")

    df = pd.read_csv(MAP_CSV, low_memory=False)
    for c in ("token","kind","mapped_code"):
        if c not in df.columns:
            raise SystemExit(f"[STOP] {MAP_CSV} missing column {c!r}; found {list(df.columns)}")

    df["token"] = df["token"].astype(str).str.strip()
    df["kind"] = df["kind"].astype(str).str.strip().str.lower()
    df["mapped_code"] = df["mapped_code"].fillna("").astype(str).str.strip().str.lower()

    # --- deterministic fills (no DB guessing) ---

    def set_map(token: str, mapped: str) -> None:
        m = df["token"].str.lower() == token.lower()
        if m.any():
            df.loc[m, "mapped_code"] = mapped.lower()

    # explicit “known” shorthands you already validated
    set_map("msg:sec61b", "mgco-4")
    set_map("2xcox8a:msg", "mgco-1")
    set_map("2xlynk:msg", "pdqm-5")
    set_map("lifeact:msg", "hc-9")
    set_map("mchilada:h2b", "pdqm-104")
    set_map("ef1a:mgold2s", "pdqm-140")
    set_map("phic-nls", "pdqm-110")
    set_map("tdmchilada:pcna", "pdqm-37")
    set_map("mgco-49_peroxisome-a2ucoe-ef1aextra-msg-skl", "mgco-49")
    set_map("mgco-52-peroxisome-a2ucoe-attb_entire+pdqm-147-abcdpmp70-msg", "mgco-52")
    set_map("mscarlet3-s2:h2b", "pdqm-117")

    # compound tokens that embed explicit basecodes
    for i, r in df.iterrows():
        if df.at[i, "mapped_code"]:
            continue
        tok = r["token"].lower()

        mg = RX_MGCO.findall(tok)
        pdqm = RX_PDQM.findall(tok)
        hc = RX_HC.findall(tok)

        out = []
        if mg:
            out += [f"mgco-{int(x)}" for x in mg]
        if pdqm:
            out += [f"pdqm-{int(x)}" for x in pdqm]
        if hc:
            out += [f"hc-{int(x)}" for x in hc]

        out = sorted(set(out))
        if out:
            df.at[i, "mapped_code"] = ",".join(out)

    # --- DB-verified fills: only accept if exactly one match ---
    eng = create_engine(db_url)

    def resolve_unique_by_fusion_token(tok: str) -> str:
        # Match tokens like "lifeact:msg" against fusion_pretty/organelle_fluors by splitting ":" into wildcards.
        # Strict: accept only if exactly one construct_code is returned.
        t = tok.lower().strip()
        pattern = "%" + "%".join([p for p in t.split(":") if p]) + "%"
        with eng.begin() as cx:
            rows = cx.execute(
                text(
                    """
                    SELECT lower(construct_code) AS base_code
                    FROM public.v_constructs_overview
                    WHERE lower(coalesce(fusion_pretty,'')) LIKE :pat
                       OR lower(coalesce(organelle_fluors,'')) LIKE :pat
                    GROUP BY lower(construct_code)
                    ORDER BY lower(construct_code)
                    """
                ),
                {"pat": pattern},
            ).fetchall()
        codes = [r[0] for r in rows if r and r[0]]
        if len(codes) == 1:
            return codes[0]
        if len(codes) == 0:
            raise SystemExit(f"[STOP] could not resolve token {tok!r} via v_constructs_overview (0 matches)")
        raise SystemExit(f"[STOP] token {tok!r} is ambiguous via v_constructs_overview ({len(codes)} matches): {codes[:20]}")

    for i, r in df.iterrows():
        if df.at[i, "mapped_code"]:
            continue
        tok = r["token"].lower()
        if r["kind"] != "construct":
            continue
        if tok in ("lifeact:msg", "2xcox8a:msg", "2xlynk:msg", "mchilada:h2b"):
            df.at[i, "mapped_code"] = resolve_unique_by_fusion_token(tok)

    # Final strictness: no blanks allowed
    blanks = df[df["mapped_code"].astype(str).str.strip() == ""]
    if not blanks.empty:
        raise SystemExit("[STOP] still have unmapped tokens:\n" + blanks[["token","kind"]].to_string(index=False))

    df.to_csv(MAP_CSV, index=False)
    print("[OK] updated", MAP_CSV, "rows", len(df))

if __name__ == "__main__":
    main()
