#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import hashlib
from typing import Dict, List, Tuple

import pandas as pd
from sqlalchemy import create_engine, text

CSV_AUTO = "seed_kits/legacy_wrangling_v3/working/exp_treatment_signatures.csv"
CSV_OVERRIDE = "seed_kits/legacy_wrangling_v3/working/exp_treatment_manual_overrides.csv"
TOKEN_MAP = "seed_kits/legacy_wrangling_v3/working/exp_treatment_token_map.csv"

BATCH_ID = "legacy_exp_treatment_signatures_v3"
INFER_SOURCE = "exp_treatment_signatures_csv"
INFER_RULE = "dataset_key+signature"
_SIG_RE = re.compile(r"^\s*plasmids=([^|]*)\|rnas=([^|]*)\|dyes=([^|]*)\s*$", re.I)
_SYN_ID_RE = re.compile(r"^(20\d{6})-plate(\d+)-slot(\d+)-roi(\d+)$", re.I)

def _s(x) -> str:
    if x is None:
        return ""
    s = str(x).strip()
    if s.lower() in ("nan", "none", "na", "n/a", "<na>"):
        return ""
    return s

def _split_csv_list(x: str) -> List[str]:
    s = _s(x).lower()
    if not s:
        return []
    parts = [p.strip() for p in s.split(",")]
    out: List[str] = []
    seen = set()
    for p in parts:
        p = p.strip()
        if not p or p in ("nan", "none", "na", "n/a", "<na>"):
            continue
        if p in seen:
            continue
        seen.add(p)
        out.append(p)
    return out

def _parse_signature(sig: str) -> Tuple[List[str], List[str], List[str]]:
    s = _s(sig)
    m = _SIG_RE.match(s)
    if not m:
        raise SystemExit(f"[STOP] signature does not match expected format: {sig!r}")
    plas = _split_csv_list(m.group(1))
    rnas = _split_csv_list(m.group(2))
    dyes_raw = _split_csv_list(m.group(3))
    dyes: List[str] = []
    for d in dyes_raw:
        d = re.sub(r"\s+", "-", d.strip().lower())
        d = re.sub(r"-{2,}", "-", d)
        if d:
            dyes.append(d)
    return (plas, rnas, dyes)

def _canon_signature(plas: List[str], rnas: List[str], dyes: List[str]) -> str:
    return f"plasmids={','.join(plas)}|rnas={','.join(rnas)}|dyes={','.join(dyes)}"

def _load_token_map() -> Dict[str, str]:
    if not os.path.exists(TOKEN_MAP):
        raise SystemExit(f"[STOP] missing token map: {TOKEN_MAP}")
    df = pd.read_csv(TOKEN_MAP, dtype=str, keep_default_na=False, na_filter=False)
    df.columns = [str(c).strip() for c in df.columns]
    need = ["token", "mapped_code"]
    missing = [c for c in need if c not in df.columns]
    if missing:
        raise SystemExit(f"[STOP] {TOKEN_MAP} missing columns {missing}; have {df.columns.tolist()}")
    out: Dict[str, str] = {}
    for r in df.itertuples(index=False):
        tok = _s(getattr(r, "token")).lower()
        code = _s(getattr(r, "mapped_code")).lower()
        if tok and code:
            out[tok] = code
    return out

def _translate_signature_tokens_to_basecodes(sig_tokens: str, tok2code: Dict[str, str]) -> str:
    plas, rnas, dyes = _parse_signature(sig_tokens)

    def xlate_list(xs: List[str]) -> List[str]:
        out: List[str] = []
        for t in xs:
            k = _s(t).lower()
            if not k:
                continue
            if k not in tok2code:
                raise SystemExit(f"[STOP] token not mapped in {TOKEN_MAP}: {t!r}")
            out.append(tok2code[k])
        seen: List[str] = []
        for x in out:
            if x not in seen:
                seen.append(x)
        return seen

    plas2 = xlate_list(plas)
    rnas2 = xlate_list(rnas)
    dyes2: List[str] = []
    for d in dyes:
        k = _s(d).lower()
        if not k:
            continue
        if k not in tok2code:
            raise SystemExit(f"[STOP] dye token not mapped in {TOKEN_MAP}: {d!r}")
        dyes2.append(tok2code[k])

    return _canon_signature(plas2, rnas2, dyes2)

def _read_mapping_csv(path: str, source_label: str, tok2code: Dict[str, str]) -> pd.DataFrame:
    df = pd.read_csv(path, dtype=str, keep_default_na=False, na_filter=False)
    df.columns = [str(c).strip() for c in df.columns]

    need_keys = ["bruker_roi_id", "dataset_key"]
    missing = [c for c in need_keys if c not in df.columns]
    if missing:
        raise SystemExit(f"[STOP] {path} missing columns {missing}; have {df.columns.tolist()}")

    df["bruker_roi_id"] = df["bruker_roi_id"].astype(str).map(_s)
    df["dataset_key"] = df["dataset_key"].astype(str).map(_s)
    df = df[(df["bruker_roi_id"] != "") & (df["dataset_key"] != "")].copy()

    candidates = []
    for c in ["signature", "signature_basecodes", "signature_tokens"]:
        if c in df.columns:
            s = df[c].astype(str).map(_s)
            nonblank = int((s.str.strip() != "").sum())
            candidates.append((c, nonblank))
    if not candidates:
        raise SystemExit(f"[STOP] {path} missing any signature column; have {df.columns.tolist()}")

    sig_col = None
    for c in ["signature", "signature_basecodes", "signature_tokens"]:
        nb = next((n for (cc, n) in candidates if cc == c), 0)
        if nb > 0:
            sig_col = c
            break
    if not sig_col:
        raise SystemExit(f"[STOP] {path} has signature columns but ALL are blank: {candidates}")

    df[sig_col] = df[sig_col].astype(str).map(_s)

    sigs: List[str] = []
    for raw in df[sig_col].tolist():
        raw = _s(raw)
        if not raw:
            sigs.append("")
            continue
        if sig_col == "signature_tokens":
            sigs.append(_translate_signature_tokens_to_basecodes(raw, tok2code))
        else:
            plas, rnas, dyes = _parse_signature(raw)
            sigs.append(_canon_signature(plas, rnas, dyes))

    df["signature"] = sigs
    df = df[df["signature"] != ""].copy()
    df["source"] = source_label
    return df[["bruker_roi_id", "dataset_key", "signature", "source"]].copy()

def _stable_treat_code(dataset_key: str, signature: str) -> str:
    s = (dataset_key or "").strip() + "||" + (signature or "").strip()
    h = hashlib.sha1(s.encode("utf-8")).hexdigest()[:10]
    return f"T-EXP-{h}"

def _parse_synth_id(roi_id: str) -> Tuple[str, int, int]:
    m = _SYN_ID_RE.match(_s(roi_id))
    if not m:
        raise SystemExit(f"[STOP] bruker_roi_id is not synthetic (expected YYYYMMDD-plateN-slotN-roiN): {roi_id!r}")
    yyyymmdd = m.group(1)
    plate_n = int(m.group(2))
    slot_n = int(m.group(3))
    roi_n = int(m.group(4))
    plate_code = f"{yyyymmdd}-plate{plate_n}"
    return (plate_code, slot_n, roi_n)

def main() -> None:
    db_url = os.environ.get("DB_URL")
    if not db_url:
        raise SystemExit("[STOP] DB_URL is not set")

    if not os.path.exists(CSV_AUTO):
        raise SystemExit(f"[STOP] missing {CSV_AUTO}")

    tok2code = _load_token_map()

    df_auto = _read_mapping_csv(CSV_AUTO, "auto", tok2code)
    df_override = _read_mapping_csv(CSV_OVERRIDE, "override", tok2code) if os.path.exists(CSV_OVERRIDE) else pd.DataFrame(columns=df_auto.columns)

    df_map = pd.concat([df_auto, df_override], ignore_index=True)
    df_map = df_map.drop_duplicates(subset=["bruker_roi_id"], keep="last").copy()

    parsed = df_map["bruker_roi_id"].apply(_parse_synth_id)
    df_map["plate_code"] = parsed.apply(lambda t: t[0])
    df_map["slot_index"] = parsed.apply(lambda t: t[1]).astype(int)
    df_map["roi_index_within_slot"] = parsed.apply(lambda t: t[2]).astype(int)

    engine = create_engine(db_url)

    plate_codes = sorted(df_map["plate_code"].unique().tolist())
    with engine.begin() as cx:
        geo = pd.read_sql(
            text("""
              SELECT
                p.plate_code,
                s.slot_index,
                ira.roi_index_within_slot,
                ira.id::text AS roi_id,
                s.id::text   AS slot_id
              FROM public.imaging_plates p
              JOIN public.imaging_slots s
                ON s.plate_id = p.id
              JOIN public.imaging_roi_annotations ira
                ON ira.slot_id = s.id
              WHERE p.plate_code = ANY(:plate_codes)
            """),
            cx,
            params={"plate_codes": plate_codes},
        )

    geo["plate_code"] = geo["plate_code"].astype(str)
    geo["slot_index"] = geo["slot_index"].astype(int)
    geo["roi_index_within_slot"] = geo["roi_index_within_slot"].astype(int)

    df_map = df_map.merge(
        geo,
        on=["plate_code", "slot_index", "roi_index_within_slot"],
        how="left",
    )

    n_resolved = int(df_map["roi_id"].notna().sum())
    if n_resolved == 0:
        raise SystemExit("[STOP] no roi_id values resolved from synthetic bruker_roi_id (plate/slot/roi).")

    with engine.begin() as cx:
        memb = pd.read_sql(
            text("""
              SELECT
                m.slot_id::text AS slot_id,
                m.clutch_id::text AS clutch_id
              FROM public.imaging_clutch_memberships m
              WHERE m.slot_id::text = ANY(:slot_ids)
                AND m.clutch_id IS NOT NULL
            """),
            cx,
            params={"slot_ids": sorted(df_map["slot_id"].dropna().unique().tolist())},
        )
    slot2clutch = dict(zip(memb["slot_id"].astype(str), memb["clutch_id"].astype(str)))

    df_map["clutch_id"] = df_map["slot_id"].astype(str).map(slot2clutch)
    n_with_clutch = int(df_map["clutch_id"].notna().sum())
    if n_with_clutch == 0:
        raise SystemExit("[STOP] no clutch_id resolved for resolved slots (imaging_clutch_memberships missing?)")

    df_map["treat_code"] = df_map.apply(lambda r: _stable_treat_code(r["dataset_key"], r["signature"]), axis=1)
    df_map["treat_text"] = df_map["signature"].astype(str)

    uniq_treats = df_map[["treat_code", "treat_text"]].drop_duplicates().copy()

    with engine.begin() as cx:
        cx.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto;"))

        cx.execute(text("""
          CREATE TEMP TABLE _tmp_treats (
            treat_code text,
            treat_text text
          ) ON COMMIT DROP;
        """))
        rows = [
            {"treat_code": str(r.treat_code), "treat_text": str(r.treat_text)}
            for r in uniq_treats.itertuples(index=False)
        ]
        if rows:
            cx.execute(
                text("INSERT INTO _tmp_treats (treat_code, treat_text) VALUES (:treat_code, :treat_text)"),
                rows,
            )

        cx.execute(text("""
          INSERT INTO public.treatments (id, treat_code, kind_code, treat_text, created_at)
          SELECT gen_random_uuid(), t.treat_code, 'injection_mix', t.treat_text, now()
          FROM _tmp_treats t
          ON CONFLICT (treat_code) DO UPDATE
          SET treat_text = EXCLUDED.treat_text;
        """))

        treat_df = pd.read_sql(
            text("""
              SELECT treat_code, id::text AS treatment_id
              FROM public.treatments
              WHERE treat_code = ANY(:codes)
            """),
            cx,
            params={"codes": sorted(uniq_treats["treat_code"].astype(str).unique().tolist())},
        )
        treat_map = dict(zip(treat_df["treat_code"].astype(str), treat_df["treatment_id"].astype(str)))

        df_map["treatment_id"] = df_map["treat_code"].astype(str).map(treat_map)
        n_with_tid = int(df_map["treatment_id"].notna().sum())
        if n_with_tid == 0:
            raise SystemExit("[STOP] no treatment_id resolved after upserting treatments")

        links = df_map[df_map["clutch_id"].notna() & df_map["treatment_id"].notna()].copy()
        links = links[["clutch_id", "treatment_id"]].drop_duplicates()

        cx.execute(text("""
          CREATE TEMP TABLE _tmp_links (
            clutch_id uuid,
            treatment_id uuid
          ) ON COMMIT DROP;
        """))
        cx.execute(
            _tmp_links_insert := text("INSERT INTO _tmp_links (clutch_id, treatment_id) VALUES (:clutch_id, :treatment_id)"),
            [{"clutch_id": r.clutch_id, "treatment_id": r.treatment_id} for r in links.itertuples(index=False)]
        )

        res = cx.execute(text("""
          INSERT INTO public.join_clutch_treatments
            (id, clutch_id, treatment_id, applied_at, created_at, notes,
             treatment_infer_source, treatment_infer_rule, treatment_infer_batch_id, treatment_inferred_at)
          SELECT
            gen_random_uuid(),
            tl.clutch_id,
            tl.treatment_id,
            now(),
            now(),
            'exp_treatment_signatures_csv',
            :src,
            :rule,
            :batch,
            now()
          FROM _tmp_links tl
          WHERE NOT EXISTS (
            SELECT 1
            FROM public.join_clutch_treatments j
            WHERE j.clutch_id = tl.clutch_id
              AND j.treatment_id = tl.treatment_id
          );
        """), {"src": INFER_SOURCE, "rule": INFER_RULE, "batch": BATCH_ID})

    print(f"[OK] resolved roi_id={n_resolved} (of {len(df_map)})")
    print(f"[OK] resolved clutch_id={n_with_clutch} (of {n_resolved})")
    print(f"[OK] upserted treatments={len(uniq_treats)}")
    print(f"[OK] inserted join_clutch_treatments={int(res.rowcount or 0)}")

if __name__ == "__main__":
    main()
