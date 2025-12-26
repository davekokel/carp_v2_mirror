from __future__ import annotations

import os
import re
import hashlib
from typing import List, Tuple

import pandas as pd
from sqlalchemy import create_engine, text

CSV_DEFAULT = "seed_kits/legacy_wrangling_v4/working/clutch_treatment_mapping_from_v4_20251225_125553.csv"

EMPTY_SIGNATURE = "plasmids=|rnas=|dyes="


INFER_SOURCE = "legacy_wrangling_v4"
INFER_RULE = "roi_csv:treatment_*_base_codes"
INFER_BATCH = "legacy_wrangling_v4"

_SIG_RE = re.compile(r"^\s*plasmids=(.*?)\|rnas=(.*?)\|dyes=(.*?)\s*$", re.I)


def _s(x) -> str:
    if x is None:
        return ""
    s = str(x).strip()
    if s.lower() in ("nan", "none", "na", "n/a", "<na>"):
        return ""
    return s


def _sig_norm(sig: str) -> str:
    s = _s(sig).strip().lower()
    s = re.sub(r"\s+", "", s)
    return s


def _is_empty_signature(sig: str) -> bool:
    return _sig_norm(sig) == "plasmids=|rnas=|dyes="


def _split_list(x: str) -> List[str]:
    s = _s(x).lower()
    if not s:
        return []
    parts = [p.strip() for p in re.split(r"[|,;]+", s) if p.strip()]
    out: List[str] = []
    seen = set()
    for p in parts:
        if p in seen:
            continue
        seen.add(p)
        out.append(p)
    return out


def _parse_sig(sig: str) -> Tuple[List[str], List[str]]:
    m = _SIG_RE.match(_s(sig))
    if not m:
        raise SystemExit(f"[STOP] bad signature format: {sig!r}")
    plas = _split_list(m.group(1))
    rnas = _split_list(m.group(2))
    return (plas, rnas)


def _stable_treat_code(sig: str) -> str:
    s = _s(sig)
    h = hashlib.sha1(s.encode("utf-8")).hexdigest()[:10]
    return f"T-EXP-{h}"


def _norm_token(x: str) -> str:
    t = _s(x).lower()
    t = re.sub(r"[^a-z0-9]+", "", t)
    t = re.sub(r"^([a-z]+)0+([0-9]+)$", r"\1\2", t)
    return t


def main() -> None:
    db_url = os.environ.get("DB_URL")
    if not db_url:
        raise SystemExit("[STOP] DB_URL is not set")

    csv_path = os.environ.get("CLUTCH_TREAT_MAP_CSV", CSV_DEFAULT)
    if not os.path.exists(csv_path):
        raise SystemExit(f"[STOP] missing CLUTCH_TREAT_MAP_CSV: {csv_path}")

    df = pd.read_csv(csv_path, low_memory=False).fillna("")
    df.columns = [str(c).strip() for c in df.columns]

    if "clutch_code" not in df.columns:
        raise SystemExit("[STOP] mapping CSV missing column: clutch_code")
    if "treat_text" not in df.columns and "signature_text" not in df.columns:
        raise SystemExit("[STOP] mapping CSV missing treat_text (or signature_text)")

    if "treat_text" not in df.columns and "signature_text" in df.columns:
        df["treat_text"] = df["signature_text"]

    df["clutch_code"] = df["clutch_code"].astype(str).map(_s)
    df["treat_text"] = df["treat_text"].astype(str).map(_s)

    # Critical: do NOT create treatments for empty signature.
    df = df[(df["clutch_code"] != "") & (df["treat_text"] != "")].copy()

    # Never load an empty-signature treatment (means: no treatment)
    df = df[df["treat_text"].map(_s) != EMPTY_SIGNATURE].copy()

    df = df[~df["treat_text"].map(_is_empty_signature)].copy()

    if len(df) == 0:
        print("[OK] no non-empty treatments to apply (mapping CSV had only empty signatures)")
        return

    if "treat_code" in df.columns:
        df["treat_code"] = df["treat_code"].astype(str).map(_s)
        missing_code = df["treat_code"].astype(str).str.strip().eq("")
        if int(missing_code.sum()):
            df.loc[missing_code, "treat_code"] = df.loc[missing_code, "treat_text"].map(_stable_treat_code)
    else:
        df["treat_code"] = df["treat_text"].map(_stable_treat_code)

    engine = create_engine(db_url)

    with engine.begin() as cx:
        cx.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto;"))

        clutches = pd.read_sql(
            text(
                """
                SELECT id::text AS clutch_id, clutch_code
                FROM public.clutches
                WHERE clutch_code = ANY(:codes)
                """
            ),
            cx,
            params={"codes": sorted(df["clutch_code"].unique().tolist())},
        )
        code2cid = dict(zip(clutches["clutch_code"].astype(str), clutches["clutch_id"].astype(str)))
        df["clutch_id"] = df["clutch_code"].map(lambda x: code2cid.get(str(x), ""))

        n_missing = int((df["clutch_id"].astype(str).str.strip() == "").sum())
        if n_missing:
            sample = (
                df[df["clutch_id"].astype(str).str.strip().eq("")][["clutch_code"]]
                .head(25)
                .to_string(index=False)
            )
            raise SystemExit("[STOP] some clutch_code values do not exist in public.clutches. Sample:\n" + sample)

        uniq_treats = df[["treat_code", "treat_text"]].drop_duplicates().copy()

        cx.execute(text("CREATE TEMP TABLE _tmp_treats (treat_code text, treat_text text) ON COMMIT DROP;"))
        cx.execute(
            text("INSERT INTO _tmp_treats (treat_code, treat_text) VALUES (:treat_code, :treat_text)"),
            [{"treat_code": r.treat_code, "treat_text": r.treat_text} for r in uniq_treats.itertuples(index=False)],
        )

        cx.execute(
            text(
                """
                INSERT INTO public.treatments (id, treat_code, kind_code, treat_text, created_at)
                SELECT gen_random_uuid(), t.treat_code, 'injection_mix', t.treat_text, now()
                FROM _tmp_treats t
                ON CONFLICT (treat_code) DO UPDATE
                SET treat_text = EXCLUDED.treat_text;
                """
            )
        )

        cx.execute(text("CREATE TEMP TABLE _tmp_treat_ids (treat_code text, treatment_id uuid, treat_text text) ON COMMIT DROP;"))
        cx.execute(
            text(
                """
                INSERT INTO _tmp_treat_ids (treat_code, treatment_id, treat_text)
                SELECT t.treat_code, tr.id, tr.treat_text
                FROM _tmp_treats t
                JOIN public.treatments tr ON tr.treat_code = t.treat_code;
                """
            )
        )

        cx.execute(
            text(
                """
                INSERT INTO public.treatment_mixes (id, treatment_id, mix_code, notes, created_at)
                SELECT gen_random_uuid(), x.treatment_id, 'M1', 'auto: legacy_wrangling_v4 clutch_treatment_mapping', now()
                FROM _tmp_treat_ids x
                LEFT JOIN public.treatment_mixes tm ON tm.treatment_id = x.treatment_id
                WHERE tm.id IS NULL
                ON CONFLICT (treatment_id) DO NOTHING;
                """
            )
        )

        cx.execute(text("CREATE TEMP TABLE _tmp_mix (treatment_id uuid, mix_id uuid) ON COMMIT DROP;"))
        cx.execute(
            text(
                """
                INSERT INTO _tmp_mix (treatment_id, mix_id)
                SELECT tm.treatment_id, tm.id
                FROM public.treatment_mixes tm
                WHERE tm.treatment_id IN (SELECT treatment_id FROM _tmp_treat_ids);
                """
            )
        )

        cx.execute(text("CREATE TEMP TABLE _tmp_ing (mix_id uuid, delivery_form text, base_code text) ON COMMIT DROP;"))

        treat_ids = pd.read_sql(text("SELECT treat_code, treatment_id::text, treat_text FROM _tmp_treat_ids"), cx)
        tid_map = dict(zip(treat_ids["treat_code"].astype(str), treat_ids["treatment_id"].astype(str)))
        ttext_map = dict(zip(treat_ids["treat_code"].astype(str), treat_ids["treat_text"].astype(str)))

        mix = pd.read_sql(text("SELECT treatment_id::text AS treatment_id, mix_id::text AS mix_id FROM _tmp_mix"), cx)
        tid2mix = dict(zip(mix["treatment_id"].astype(str), mix["mix_id"].astype(str)))

        ing_rows = []
        for r in uniq_treats.itertuples(index=False):
            tc = str(r.treat_code)
            tid = tid_map.get(tc, "")
            mxid = tid2mix.get(tid, "")
            sig = ttext_map.get(tc, "")
            plas, rnas = _parse_sig(sig)
            for b in plas:
                if _s(mxid) and _s(b):
                    ing_rows.append({"mix_id": mxid, "delivery_form": "plasmid", "base_code": _s(b)})
            for b in rnas:
                if _s(mxid) and _s(b):
                    ing_rows.append({"mix_id": mxid, "delivery_form": "rna", "base_code": _s(b)})

        if ing_rows:
            cx.execute(
                text(
                    "INSERT INTO _tmp_ing (mix_id, delivery_form, base_code) "
                    "VALUES (CAST(:mix_id AS uuid), :delivery_form, :base_code)"
                ),
                ing_rows,
            )

        cons = pd.read_sql(
            text(
                """
                SELECT id::text AS construct_id, base_code
                FROM public.constructs
                WHERE coalesce(btrim(base_code),'') <> ''
                """
            ),
            cx,
        )
        cons["base_norm"] = cons["base_code"].astype(str).map(_norm_token)
        base2cid = dict(zip(cons["base_norm"].astype(str), cons["construct_id"].astype(str)))

        missing = []
        for b in pd.read_sql(text("SELECT DISTINCT base_code FROM _tmp_ing"), cx)["base_code"].astype(str).tolist():
            if _norm_token(b) not in base2cid:
                missing.append(b)
        if missing:
            sample = ", ".join(missing[:40])
            raise SystemExit("[STOP] unmapped construct base_code(s) in mapping CSV (need constructs present): " + sample)

        cx.execute(text("CREATE TEMP TABLE _tmp_ing_res (mix_id uuid, delivery_form text, construct_id uuid) ON COMMIT DROP;"))
        rows = []
        for r in pd.read_sql(text("SELECT mix_id::text, delivery_form, base_code FROM _tmp_ing"), cx).itertuples(index=False):
            cid = base2cid.get(_norm_token(r.base_code), "")
            rows.append({"mix_id": r.mix_id, "delivery_form": r.delivery_form, "construct_id": cid})
        cx.execute(
            text(
                "INSERT INTO _tmp_ing_res (mix_id, delivery_form, construct_id) "
                "VALUES (CAST(:mix_id AS uuid), :delivery_form, CAST(:construct_id AS uuid))"
            ),
            rows,
        )

        cx.execute(
            text(
                """
                INSERT INTO public.treatment_mix_constructs (id, mix_id, construct_id, created_at, delivery_form)
                SELECT gen_random_uuid(), r.mix_id, r.construct_id, now(), r.delivery_form
                FROM _tmp_ing_res r
                WHERE NOT EXISTS (
                  SELECT 1
                  FROM public.treatment_mix_constructs tmc
                  WHERE tmc.mix_id = r.mix_id
                    AND tmc.construct_id = r.construct_id
                    AND coalesce(btrim(tmc.delivery_form),'') = coalesce(btrim(r.delivery_form),'')
                );
                """
            )
        )

        df_apply = df[["clutch_id", "clutch_code", "treat_code"]].drop_duplicates().copy()

        treats2 = pd.read_sql(
            text(
                """
                SELECT treat_code, id::text AS treatment_id
                FROM public.treatments
                WHERE treat_code = ANY(:codes)
                """
            ),
            cx,
            params={"codes": sorted(df_apply["treat_code"].astype(str).unique().tolist())},
        )
        tc2tid = dict(zip(treats2["treat_code"].astype(str), treats2["treatment_id"].astype(str)))
        df_apply["treatment_id"] = df_apply["treat_code"].map(lambda x: tc2tid.get(str(x), ""))

        cx.execute(text("CREATE TEMP TABLE _tmp_apply (clutch_id uuid, clutch_code text, treatment_id uuid) ON COMMIT DROP;"))
        cx.execute(
            text(
                "INSERT INTO _tmp_apply (clutch_id, clutch_code, treatment_id) "
                "VALUES (CAST(:clutch_id AS uuid), :clutch_code, CAST(:treatment_id AS uuid))"
            ),
            [{"clutch_id": r.clutch_id, "clutch_code": r.clutch_code, "treatment_id": r.treatment_id} for r in df_apply.itertuples(index=False)],
        )

        cx.execute(
            text(
                """
                DELETE FROM public.join_clutch_treatments j
                WHERE j.clutch_id IN (SELECT clutch_id FROM _tmp_apply)
                  AND j.treatment_infer_source = :src
                  AND j.treatment_infer_rule   = :rule
                  AND j.treatment_infer_batch_id = :batch;
                """
            ),
            {"src": INFER_SOURCE, "rule": INFER_RULE, "batch": INFER_BATCH},
        )

        cx.execute(
            text(
                """
                INSERT INTO public.join_clutch_treatments
                  (id, clutch_id, treatment_id, applied_at, created_at, notes,
                   treatment_infer_source, treatment_infer_rule, treatment_infer_batch_id, treatment_inferred_at)
                SELECT
                  gen_random_uuid(),
                  a.clutch_id,
                  a.treatment_id,
                  now(),
                  now(),
                  'legacy_wrangling_v4 clutch_treatment_mapping',
                  :src,
                  :rule,
                  :batch,
                  now()
                FROM _tmp_apply a
                WHERE NOT EXISTS (
                  SELECT 1
                  FROM public.join_clutch_treatments j
                  WHERE j.clutch_id = a.clutch_id
                    AND j.treatment_id = a.treatment_id
                );
                """
            ),
            {"src": INFER_SOURCE, "rule": INFER_RULE, "batch": INFER_BATCH},
        )

        cx.execute(
            text(
                """
                UPDATE public.imaging_clutch_memberships m
                SET treated_clutch_id = NULL
                WHERE m.clutch_id IN (SELECT clutch_id FROM _tmp_apply);
                """
            )
        )

        cx.execute(
            text(
                """
                DELETE FROM public.treated_clutches_v11 tc
                WHERE tc.clutch_id IN (SELECT clutch_id FROM _tmp_apply);
                """
            )
        )

        cx.execute(
            text(
                """
                INSERT INTO public.treated_clutches_v11 (
                  id, clutch_id, treated_clutch_code, treatment_id, n_embryos, notes, created_at, created_by
                )
                SELECT
                  gen_random_uuid(),
                  a.clutch_id,
                  ('TREAT-' || a.clutch_code || '-00'),
                  a.treatment_id,
                  NULL,
                  'seed_from_clutch_treatment_mapping_v4',
                  now(),
                  'v11_apply_clutch_treatment_mapping_from_v4'
                FROM _tmp_apply a
                ON CONFLICT (clutch_id, treatment_id) DO NOTHING;
                """
            )
        )

        cx.execute(
            text(
                """
                UPDATE public.imaging_clutch_memberships m
                SET treated_clutch_id = tc.id
                FROM public.treated_clutches_v11 tc
                JOIN _tmp_apply a ON a.clutch_id = tc.clutch_id AND a.treatment_id = tc.treatment_id
                WHERE m.clutch_id = a.clutch_id;
                """
            )
        )

    print("[OK] applied clutch treatment mapping:", csv_path)
    print("[OK] clutches:", int(df["clutch_code"].nunique()))
    print("[OK] unique treatments:", int(df["treat_code"].nunique()))


if __name__ == "__main__":
    main()
