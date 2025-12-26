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

    # Optional override metadata (present in override CSV; defaulted for auto)
    if "override_kind" not in df.columns:
        df["override_kind"] = ""
    if "override_note" not in df.columns:
        df["override_note"] = ""
    if "override_locked" not in df.columns:
        df["override_locked"] = ""

    out_cols = ["bruker_roi_id", "dataset_key", "signature", "source", "override_kind", "override_note", "override_locked"]
    return df[out_cols].copy()

def _stable_treat_code(dataset_key: str, signature: str) -> str:
    s = (signature or "").strip()
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

    # Locked override rows must always win (never overwritten by scripts).
    # Priority:
    #   1) override_locked true
    #   2) source == "override"
    # Then dedupe by bruker_roi_id.
    df_map["override_locked"] = (
        df_map["override_locked"]
        .astype(str)
        .str.strip()
        .str.lower()
        .isin(["1", "t", "true", "yes", "y"])
    )
    df_map["_prio_locked"] = df_map["override_locked"].astype(int)
    df_map["_prio_source"] = (df_map["source"].astype(str) == "override").astype(int)
    df_map = df_map.sort_values(["bruker_roi_id", "_prio_locked", "_prio_source"], ascending=[True, False, False])
    df_map = df_map.drop_duplicates(subset=["bruker_roi_id"], keep="first").copy()
    df_map = df_map.drop(columns=["_prio_locked", "_prio_source"])

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

    def _sig_norm(x: object) -> str:
        s = "" if x is None else str(x)
        s = s.strip().lower().replace(" ", "")
        return s

    # STRICT: empty signature is NOT a treatment; skip it.
    empty_mask = df_map["treat_text"].map(lambda x: _sig_norm(x) == "plasmids=|rnas=|dyes=")
    n_empty = int(empty_mask.sum())
    if n_empty:
        print(f"[WARN] exp_sig: skipping empty signatures (plasmids=|rnas=|dyes=): {n_empty}")
        df_map = df_map[~empty_mask].copy()

    # STRICT: refuse legacy junk like "dye-<uuid8>" in signatures (must be fixed upstream).
    bad_dye = df_map["treat_text"].astype(str).str.contains(r"dye-", case=False, na=False)
    n_bad_dye = int(bad_dye.sum())
    if n_bad_dye:
        sample = (
            df_map.loc[bad_dye, ["dataset_key", "bruker_roi_id", "treat_text"]]
            .head(25)
            .to_string(index=False)
        )
        raise SystemExit("[STOP] exp_sig: found illegal dye-* tokens in signature; fix token map upstream.\nSample:\n" + sample)

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
        cx.execute(text("CREATE TEMP TABLE _tmp_treat_ids (treat_code text, treatment_id uuid, treat_text text) ON COMMIT DROP;"))
        cx.execute(text("""
          INSERT INTO _tmp_treat_ids (treat_code, treatment_id, treat_text)
          SELECT t.treat_code, tr.id, tr.treat_text
          FROM _tmp_treats t
          JOIN public.treatments tr ON tr.treat_code = t.treat_code;
        """))

        cx.execute(text("""
          INSERT INTO public.treatment_mixes (id, treatment_id, mix_code, notes, created_at)
          SELECT gen_random_uuid(), x.treatment_id, 'M1', 'auto: exp_sig', now()
          FROM _tmp_treat_ids x
          LEFT JOIN public.treatment_mixes tm ON tm.treatment_id = x.treatment_id
          WHERE tm.id IS NULL
          ON CONFLICT (treatment_id) DO NOTHING;
        """))

        cx.execute(text("CREATE TEMP TABLE _tmp_mix (treatment_id uuid, mix_id uuid) ON COMMIT DROP;"))
        cx.execute(text("""
          INSERT INTO _tmp_mix (treatment_id, mix_id)
          SELECT tm.treatment_id, tm.id
          FROM public.treatment_mixes tm
          WHERE tm.treatment_id IN (SELECT treatment_id FROM _tmp_treat_ids);
        """))

        cx.execute(text("CREATE TEMP TABLE _tmp_tokens (mix_id uuid, delivery_form text, token_raw text, token_norm text) ON COMMIT DROP;"))
        cx.execute(text("""
          WITH sig AS (
            SELECT
              m.mix_id,
              x.treat_text,
              split_part(split_part(x.treat_text, 'plasmids=', 2), '|', 1) AS plas,
              split_part(split_part(x.treat_text, 'rnas=', 2), '|', 1)     AS rnas,
              split_part(split_part(x.treat_text, 'dyes=', 2), '|', 1)     AS dyes
            FROM _tmp_treat_ids x
            JOIN _tmp_mix m ON m.treatment_id = x.treatment_id
          ),
          plas AS (
            SELECT mix_id, 'plasmid'::text AS delivery_form, btrim(tok) AS tok
            FROM sig, regexp_split_to_table(coalesce(plas,''), ',') tok
            WHERE btrim(tok) <> ''
          ),
          rnas AS (
            SELECT mix_id, 'rna'::text AS delivery_form, btrim(tok) AS tok
            FROM sig, regexp_split_to_table(coalesce(rnas,''), ',') tok
            WHERE btrim(tok) <> ''
          ),
          dyes AS (
            SELECT mix_id, 'dye'::text AS delivery_form, btrim(tok) AS tok
            FROM sig, regexp_split_to_table(coalesce(dyes,''), ',') tok
            WHERE btrim(tok) <> ''
          ),
          all_tok AS (
            SELECT * FROM plas
            UNION ALL SELECT * FROM rnas
            UNION ALL SELECT * FROM dyes
          )
          INSERT INTO _tmp_tokens (mix_id, delivery_form, token_raw, token_norm)
          SELECT
            mix_id,
            delivery_form,
            tok,
            regexp_replace(
              lower(regexp_replace(tok, '[^a-zA-Z0-9]+', '', 'g')),
              '^([a-z]+)0+([0-9]+)$',
              '\\1\\2'
            ) AS token_norm
          FROM all_tok;
        """))

        cx.execute(text("CREATE TEMP TABLE _tmp_construct_resolved (mix_id uuid, construct_id uuid, delivery_form text) ON COMMIT DROP;"))
        cx.execute(text("""
          WITH c AS (
            SELECT
              id AS construct_id,
              regexp_replace(
                lower(regexp_replace(base_code, '[^a-zA-Z0-9]+', '', 'g')),
                '^([a-z]+)0+([0-9]+)$',
                '\\1\\2'
              ) AS base_norm
            FROM public.constructs
            WHERE coalesce(btrim(base_code),'') <> ''
          ),
          want AS (
            SELECT mix_id, delivery_form, token_raw, token_norm
            FROM _tmp_tokens
            WHERE delivery_form IN ('plasmid','rna')
          ),
          j AS (
            SELECT w.mix_id, w.delivery_form, w.token_raw, w.token_norm, c.construct_id
            FROM want w
            LEFT JOIN c ON c.base_norm = w.token_norm
          )
          INSERT INTO _tmp_construct_resolved (mix_id, construct_id, delivery_form)
          SELECT mix_id, construct_id, delivery_form
          FROM j
          WHERE construct_id IS NOT NULL;
        """))

        missing_constructs = cx.execute(text("""
          WITH want AS (
            SELECT DISTINCT token_raw, token_norm
            FROM _tmp_tokens
            WHERE delivery_form IN ('plasmid','rna')
          ),
          c AS (
            SELECT DISTINCT lower(regexp_replace(base_code, '[^a-zA-Z0-9]+', '', 'g')) AS base_norm
            FROM public.constructs
            WHERE coalesce(btrim(base_code),'') <> ''
          )
          SELECT w.token_raw
          FROM want w
          LEFT JOIN c ON c.base_norm = w.token_norm
          WHERE c.base_norm IS NULL
          ORDER BY w.token_raw;
        """)).fetchall()
        if missing_constructs:
            sample = ", ".join([r[0] for r in missing_constructs[:30]])
            raise SystemExit(f"[STOP] exp_sig: unmapped construct base_code tokens: {sample}")

        cx.execute(text("CREATE TEMP TABLE _tmp_dye_resolved (mix_id uuid, dye_id uuid) ON COMMIT DROP;"))
        cx.execute(text("""
          WITH d AS (
            SELECT
              id AS dye_id,
              lower(regexp_replace(coalesce(nickname,''), '[^a-zA-Z0-9]+', '', 'g')) AS nick_norm
            FROM public.dyes
            WHERE coalesce(btrim(nickname),'') <> ''
          ),
          want AS (
            SELECT DISTINCT mix_id, token_raw, token_norm
            FROM _tmp_tokens
            WHERE delivery_form = 'dye'
          ),
          j AS (
            SELECT w.mix_id, w.token_raw, w.token_norm, d.dye_id
            FROM want w
            LEFT JOIN d ON d.nick_norm = w.token_norm
          )
          INSERT INTO _tmp_dye_resolved (mix_id, dye_id)
          SELECT mix_id, dye_id
          FROM j
          WHERE dye_id IS NOT NULL;
        """))

        missing_dyes = cx.execute(text("""
          WITH want AS (
            SELECT DISTINCT token_raw, token_norm
            FROM _tmp_tokens
            WHERE delivery_form = 'dye'
          ),
          d AS (
            SELECT DISTINCT lower(regexp_replace(coalesce(nickname,''), '[^a-zA-Z0-9]+', '', 'g')) AS nick_norm
            FROM public.dyes
            WHERE coalesce(btrim(nickname),'') <> ''
          )
          SELECT w.token_raw
          FROM want w
          LEFT JOIN d ON d.nick_norm = w.token_norm
          WHERE d.nick_norm IS NULL
          ORDER BY w.token_raw;
        """)).fetchall()
        if missing_dyes:
            sample = ", ".join([r[0] for r in missing_dyes[:30]])
            raise SystemExit(f"[STOP] exp_sig: unmapped dye nicknames: {sample}")

        cx.execute(text("""
          INSERT INTO public.treatment_mix_constructs (id, mix_id, construct_id, created_at, delivery_form)
          SELECT
            gen_random_uuid(),
            r.mix_id,
            r.construct_id,
            now(),
            r.delivery_form
          FROM _tmp_construct_resolved r
          WHERE NOT EXISTS (
            SELECT 1
            FROM public.treatment_mix_constructs tmc
            WHERE tmc.mix_id = r.mix_id
              AND tmc.construct_id = r.construct_id
              AND coalesce(btrim(tmc.delivery_form),'') = coalesce(btrim(r.delivery_form),'')
          );
        """))

        cx.execute(text("""
          INSERT INTO public.treatment_mix_dyes (id, mix_id, dye_id, created_at)
          SELECT
            gen_random_uuid(),
            r.mix_id,
            r.dye_id,
            now()
          FROM _tmp_dye_resolved r
          WHERE NOT EXISTS (
            SELECT 1
            FROM public.treatment_mix_dyes tmd
            WHERE tmd.mix_id = r.mix_id
              AND tmd.dye_id = r.dye_id
          );
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

        # Per-row provenance so overrides can be distinguished (and never overwritten by auto).
        links["source"] = links.get("source", "").astype(str)
        links["override_locked"] = (
            links.get("override_locked", "")
            .astype(str)
            .str.strip()
            .str.lower()
            .isin(["1", "t", "true", "yes", "y"])
        )
        links["override_kind"] = links.get("override_kind", "").astype(str)

        AUTO_SRC = INFER_SOURCE
        AUTO_RULE = INFER_RULE
        AUTO_BATCH = BATCH_ID

        OVR_SRC = "exp_treatment_manual_override"
        OVR_RULE = "override:bruker_roi_id+signature"
        OVR_BATCH = "legacy_exp_treatment_manual_overrides_v3"

        def _infer_src(r) -> str:
            if r["source"] == "override" and bool(r["override_locked"]):
                return OVR_SRC
            return AUTO_SRC

        def _infer_rule(r) -> str:
            if r["source"] == "override" and bool(r["override_locked"]):
                return OVR_RULE
            return AUTO_RULE

        def _infer_batch(r) -> str:
            if r["source"] == "override" and bool(r["override_locked"]):
                return OVR_BATCH
            return AUTO_BATCH

        links["infer_source"] = links.apply(_infer_src, axis=1)
        links["infer_rule"] = links.apply(_infer_rule, axis=1)
        links["infer_batch"] = links.apply(_infer_batch, axis=1)

        links = links[["clutch_id", "treatment_id", "infer_source", "infer_rule", "infer_batch"]].drop_duplicates()

        cx.execute(text("""
          CREATE TEMP TABLE _tmp_links (
            clutch_id uuid,
            treatment_id uuid,
            infer_source text,
            infer_rule text,
            infer_batch text
          ) ON COMMIT DROP;
        """))
        cx.execute(
            text(
                "INSERT INTO _tmp_links (clutch_id, treatment_id, infer_source, infer_rule, infer_batch) "
                "VALUES (:clutch_id, :treatment_id, :infer_source, :infer_rule, :infer_batch)"
            ),
            [
                {
                    "clutch_id": r.clutch_id,
                    "treatment_id": r.treatment_id,
                    "infer_source": r.infer_source,
                    "infer_rule": r.infer_rule,
                    "infer_batch": r.infer_batch,
                }
                for r in links.itertuples(index=False)
            ],
        )

        # Delete only rows we own for the SAME (source, rule, batch) we’re about to write.
        cx.execute(
            text(
                """
                DELETE FROM public.join_clutch_treatments j
                WHERE EXISTS (
                  SELECT 1
                  FROM _tmp_links tl
                  WHERE tl.clutch_id = j.clutch_id
                    AND tl.infer_source = j.treatment_infer_source
                    AND tl.infer_rule   = j.treatment_infer_rule
                    AND tl.infer_batch  = j.treatment_infer_batch_id
                );
                """
            )
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
            tl.infer_source,
            tl.infer_rule,
            tl.infer_batch,
            now()
          FROM _tmp_links tl
          ON CONFLICT (clutch_id, treatment_id) DO NOTHING;
        """))

    print(f"[OK] resolved roi_id={n_resolved} (of {len(df_map)})")
    print(f"[OK] resolved clutch_id={n_with_clutch} (of {n_resolved})")
    print(f"[OK] upserted treatments={len(uniq_treats)}")
    print(f"[OK] inserted join_clutch_treatments={int(res.rowcount or 0)}")

if __name__ == "__main__":
    main()
