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

_SIG_RE = re.compile(r"^\s*plasmids=([^|]*)\|rnas=([^|]*)\|dyes=([^|]*)\s*$", re.I)


def _stable_treat_code(dataset_key: str, signature: str) -> str:
    s = (dataset_key or "").strip() + "||" + (signature or "").strip()
    h = hashlib.sha1(s.encode("utf-8")).hexdigest()[:10]
    return f"T-EXP-{h}"


def _s(x) -> str:
    if x is None:
        return ""
    s = str(x).strip()
    if s.lower() in ("nan", "none"):
        return ""
    return s


def _alnum_key(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", _s(s).lower())


def _split_csv_list(x: str) -> List[str]:
    s = _s(x).lower()
    if not s:
        return []
    parts = [p.strip() for p in s.split(",")]
    out: List[str] = []
    seen = set()
    for p in parts:
        p = p.strip()
        if not p or p in ("nan", "none"):
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
        d = d.strip().lower()
        if not d:
            continue
        d = re.sub(r"\s+", "-", d)
        d = re.sub(r"-{2,}", "-", d)
        dyes.append(d)

    return (plas, rnas, dyes)


def _canon_signature(plas: List[str], rnas: List[str], dyes: List[str]) -> str:
    return f"plasmids={','.join(plas)}|rnas={','.join(rnas)}|dyes={','.join(dyes)}"


def _load_token_map() -> Dict[str, str]:
    if not os.path.exists(TOKEN_MAP):
        raise SystemExit(f"[STOP] missing token map: {TOKEN_MAP}")

    df = pd.read_csv(TOKEN_MAP, dtype=str, keep_default_na=False, na_filter=False)
    df.columns = [str(c).strip() for c in df.columns]

    need = ["token", "kind", "mapped_code"]
    missing = [c for c in need if c not in df.columns]
    if missing:
        raise SystemExit(f"[STOP] {TOKEN_MAP} missing columns {missing}; have {df.columns.tolist()}")

    out: Dict[str, str] = {}
    for r in df.itertuples(index=False):
        tok = _s(getattr(r, "token")).lower()
        code = _s(getattr(r, "mapped_code")).lower()
        if not tok:
            continue
        if not code:
            continue
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
            if k in tok2code:
                out.append(tok2code[k])
            else:
                raise SystemExit(f"[STOP] token not mapped in {TOKEN_MAP}: {t!r}")
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
        if k in tok2code:
            dyes2.append(tok2code[k])
        else:
            raise SystemExit(f"[STOP] dye token not mapped in {TOKEN_MAP}: {d!r}")

    return _canon_signature(plas2, rnas2, dyes2)


def _read_mapping_csv(path: str, source_label: str, tok2code: Dict[str, str]) -> pd.DataFrame:
    df = pd.read_csv(path, dtype=str, keep_default_na=False, na_filter=False)
    df.columns = [str(c).strip() for c in df.columns]

    need_keys = ["bruker_roi_id", "dataset_key"]
    missing = [c for c in need_keys if c not in df.columns]
    if missing:
        raise SystemExit(f"[STOP] {path} missing columns {missing}; have {df.columns.tolist()}")

    # Normalize key columns first
    df["bruker_roi_id"] = df["bruker_roi_id"].astype(str).map(_s)
    df["dataset_key"] = df["dataset_key"].astype(str).map(_s)

    df = df[df["bruker_roi_id"] != ""]
    df = df[df["dataset_key"] != ""]

    # Choose the signature source deterministically by NONBLANK COUNTS.
    # Priority:
    #  1) signature (already basecodes) if populated
    #  2) signature_basecodes if populated
    #  3) signature_tokens (translate via token_map) if populated
    # No guessing, no silent fallback; we print counts via hard errors.
    candidates = []
    for c in ["signature", "signature_basecodes", "signature_tokens"]:
        if c in df.columns:
            s = df[c].astype(str).map(_s)
            nonblank = int((s.str.strip() != "").sum())
            candidates.append((c, nonblank))

    if not candidates:
        raise SystemExit(f"[STOP] {path} missing any signature column; have {df.columns.tolist()}")

    # pick the first column in priority order that has any nonblank
    sig_col = None
    for c in ["signature", "signature_basecodes", "signature_tokens"]:
        nb = next((n for (cc, n) in candidates if cc == c), 0)
        if nb > 0:
            sig_col = c
            break

    if not sig_col:
        raise SystemExit(f"[STOP] {path} has signature columns but ALL are blank: {candidates}")

    df[sig_col] = df[sig_col].astype(str).map(_s)

    # Normalize to a final 'signature' column (basecodes only)
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
    df = df[df["signature"] != ""]

    df["source"] = source_label
    return df[["bruker_roi_id", "dataset_key", "signature", "source"]].copy()


def main() -> None:
    db_url = os.environ.get("DB_URL")
    if not db_url:
        raise SystemExit("[STOP] DB_URL is not set")

    if not os.path.exists(CSV_AUTO):
        raise SystemExit(f"[STOP] missing {CSV_AUTO}")

    tok2code = _load_token_map()
    rev_code_to_token = {v: k for (k, v) in tok2code.items() if v}

    df_auto = _read_mapping_csv(CSV_AUTO, "auto", tok2code)

    if os.path.exists(CSV_OVERRIDE):
        df_ovr = _read_mapping_csv(CSV_OVERRIDE, "override", tok2code)
    else:
        df_ovr = pd.DataFrame(columns=["bruker_roi_id", "dataset_key", "signature", "source"])

    df = pd.concat([df_auto, df_ovr], ignore_index=True)

    df = (
        df.sort_values(["dataset_key", "bruker_roi_id", "source"])
          .drop_duplicates(subset=["dataset_key", "bruker_roi_id"], keep="last")
          .reset_index(drop=True)
    )

    bad = df.groupby(["dataset_key", "bruker_roi_id"])["signature"].nunique()
    bad = bad[bad > 1]
    if not bad.empty:
        raise SystemExit(f"[STOP] ambiguous signatures per ROI (first 10): {bad.head(10).to_dict()}")

    eng = create_engine(db_url)

    with eng.begin() as cx:
        df_map = pd.read_sql(
            text(
                """
                SELECT
                  ra.roi_code,
                  ra.slot_id::text AS slot_id,
                  icm.clutch_id::text AS clutch_id
                FROM public.imaging_roi_annotations ra
                JOIN public.imaging_clutch_memberships icm
                  ON icm.slot_id = ra.slot_id
                """
            ),
            cx,
        )
        df_map["roi_code"] = df_map["roi_code"].astype(str).map(_s)
        df_map["slot_id"] = df_map["slot_id"].astype(str).map(_s)
        df_map["clutch_id"] = df_map["clutch_id"].astype(str).map(_s)

        df2 = df.merge(df_map, left_on="bruker_roi_id", right_on="roi_code", how="inner")
        if df2.empty:
            raise SystemExit("[STOP] no ROI ids matched DB roi_code")

        df_cl = pd.read_sql(text("SELECT id::text AS clutch_id, clutch_code FROM public.clutches"), cx)
        clutch_id_to_code: Dict[str, str] = dict(zip(df_cl["clutch_id"].astype(str), df_cl["clutch_code"].astype(str)))

        df2["treat_code"] = df2.apply(lambda r: _stable_treat_code(str(r["dataset_key"]), str(r["signature"])), axis=1)
        df2["treat_text"] = df2.apply(lambda r: f"{r['dataset_key']} :: {r['signature']}", axis=1)

        ins_treat = text(
            """
            INSERT INTO public.treatments (id, kind_code, treat_code, treat_text, created_at)
            VALUES (gen_random_uuid(), 'legacy', :treat_code, :treat_text, now())
            ON CONFLICT (treat_code) DO UPDATE
              SET treat_text = EXCLUDED.treat_text
            RETURNING id::text;
            """
        )

        ensure_mix = text(
            """
            INSERT INTO public.treatment_mixes (treatment_id, mix_code, notes, created_at)
            VALUES (:treatment_id, 'M1', 'auto: v11_apply_exp_treatment_signatures_csv', now())
            ON CONFLICT (treatment_id, mix_code)
            DO UPDATE SET notes = EXCLUDED.notes
            RETURNING id::text;
            """
        )

        get_mix = text(
            """
            SELECT id::text
            FROM public.treatment_mixes
            WHERE treatment_id = :treatment_id AND mix_code = 'M1'
            LIMIT 1;
            """
        )

        get_construct_id = text(
            """
            SELECT id::text
            FROM public.constructs
            WHERE lower(base_code) = :base_code
            LIMIT 1;
            """
        )

        ins_mix_construct = text(
            """
            INSERT INTO public.treatment_mix_constructs (mix_id, construct_id, delivery_form)
            VALUES (:mix_id, :construct_id, :delivery_form)
            ON CONFLICT DO NOTHING;
            """
        )

        get_dye_id = text(
            """
            SELECT id::text
            FROM public.dyes
            WHERE regexp_replace(lower(btrim(code)),        '[^a-z0-9]+', '', 'g') = :k
               OR regexp_replace(lower(btrim(nickname)),    '[^a-z0-9]+', '', 'g') = :k
               OR regexp_replace(lower(btrim(display_name)),'[^a-z0-9]+', '', 'g') = :k
            LIMIT 2;
            """
        )

        ins_mix_dye = text(
            """
            INSERT INTO public.treatment_mix_dyes (mix_id, dye_id)
            VALUES (:mix_id, :dye_id)
            ON CONFLICT DO NOTHING;
            """
        )

        ins_tc = text(
            """
            INSERT INTO public.treated_clutches_v11
              (id, clutch_id, treated_clutch_code, treatment_id, n_embryos, notes, created_by, created_at)
            VALUES
              (gen_random_uuid(), :clutch_id, :treated_clutch_code, :treatment_id, NULL, :notes, 'v11_apply_exp_treatment_signatures_csv', now())
            ON CONFLICT (clutch_id, treatment_id)
            DO UPDATE SET
              treated_clutch_code = EXCLUDED.treated_clutch_code,
              notes = EXCLUDED.notes
            RETURNING id::text;
            """
        )

        upd_membership_slot = text(
            """
            UPDATE public.imaging_clutch_memberships
            SET treated_clutch_id = :treated_clutch_id
            WHERE clutch_id = :clutch_id AND slot_id = :slot_id;
            """
        )


        get_clutch_genotype_id = text(
            """
            SELECT cg.id::text
            FROM public.clutch_genotypes_v11 cg
            JOIN public.clutches c ON c.id = cg.clutch_id
            WHERE c.id = CAST(:clutch_id AS uuid)
              AND cg.genotype_v11_id = c.genotype_v11_id
            LIMIT 1;
            """
        )

        ins_tcg = text(
            """
            INSERT INTO public.treated_clutch_genotypes_v11 (
              id, treated_clutch_id, clutch_genotype_id, is_primary, created_at, created_by
            )
            VALUES (
              gen_random_uuid(),
              CAST(:treated_clutch_id AS uuid),
              CAST(:clutch_genotype_id AS uuid),
              true, now(), 'v11_apply_exp_treatment_signatures_csv'
            )
            ON CONFLICT (treated_clutch_id, clutch_genotype_id)
            DO UPDATE SET is_primary = true;
            """
        )

        rows = (
            df2[["dataset_key", "signature", "treat_code", "treat_text", "clutch_id", "slot_id"]]
            .drop_duplicates()
            .reset_index(drop=True)
        )

        treat_code_to_id: Dict[str, str] = {}
        n_treat = 0
        n_tc = 0
        n_upd = 0

        for _, r in rows.iterrows():
            dataset_key = str(r["dataset_key"])
            signature = str(r["signature"])
            treat_code = str(r["treat_code"])
            treat_text = str(r["treat_text"])
            clutch_id = str(r["clutch_id"])
            slot_id = str(r["slot_id"])

            if clutch_id not in clutch_id_to_code:
                raise SystemExit(f"[STOP] clutch_id not found in clutches: {clutch_id}")

            if treat_code not in treat_code_to_id:
                treatment_id = cx.execute(ins_treat, {"treat_code": treat_code, "treat_text": treat_text}).scalar()
                if not treatment_id:
                    raise SystemExit(f"[STOP] failed to upsert treatment for treat_code={treat_code}")
                treat_code_to_id[treat_code] = treatment_id
                n_treat += 1
            else:
                treatment_id = treat_code_to_id[treat_code]

            mix_id = cx.execute(ensure_mix, {"treatment_id": treatment_id}).scalar()
            if not mix_id:
                mix_id = cx.execute(get_mix, {"treatment_id": treatment_id}).scalar()
            if not mix_id:
                raise SystemExit(f"[STOP] failed to ensure mix M1 for treatment_id={treatment_id}")

            plas, rnas, dyes = _parse_signature(signature)

            for base_code in plas:
                cid = cx.execute(get_construct_id, {"base_code": base_code}).scalar()
                if not cid:
                    raise SystemExit(f"[STOP] unknown construct base_code {base_code!r} (treat_code={treat_code}, dataset_key={dataset_key})")
                cx.execute(ins_mix_construct, {"mix_id": mix_id, "construct_id": cid, "delivery_form": "plasmid"})

            for base_code in rnas:
                cid = cx.execute(get_construct_id, {"base_code": base_code}).scalar()
                if not cid:
                    raise SystemExit(f"[STOP] unknown construct base_code {base_code!r} (treat_code={treat_code}, dataset_key={dataset_key})")
                cx.execute(ins_mix_construct, {"mix_id": mix_id, "construct_id": cid, "delivery_form": "rna"})

            for dye in dyes:
                d_raw = str(dye).strip().lower()
                if not d_raw:
                    continue
                if d_raw in rev_code_to_token:
                    d_raw = rev_code_to_token[d_raw]
                k = _alnum_key(d_raw)
                rows_d = cx.execute(get_dye_id, {"k": k}).fetchall()
                ids = sorted({rr[0] for rr in rows_d if rr and rr[0]})
                if len(ids) == 0:
                    raise SystemExit(f"[STOP] unknown dye token {d_raw!r} (treat_code={treat_code}, dataset_key={dataset_key})")
                if len(ids) > 1:
                    raise SystemExit(f"[STOP] ambiguous dye token {d_raw!r} matched {ids} (treat_code={treat_code}, dataset_key={dataset_key})")
                cx.execute(ins_mix_dye, {"mix_id": mix_id, "dye_id": ids[0]})
            clutch_code = clutch_id_to_code[clutch_id]
            base = clutch_code.replace("LCL-", "TCL-", 1) if clutch_code.startswith("LCL-") else f"TCL-{clutch_code}"
            treated_code = f"{base}-{treat_code[-6:]}"
            notes = treat_text

            tclid = cx.execute(
                ins_tc,
                {"clutch_id": clutch_id, "treated_clutch_code": treated_code, "treatment_id": treatment_id, "notes": notes},
            ).scalar()
            if not tclid:
                raise SystemExit(f"[STOP] failed to upsert treated_clutches_v11 for clutch_id={clutch_id} treat_code={treat_code}")

            clutch_genotype_id = cx.execute(get_clutch_genotype_id, {"clutch_id": clutch_id}).scalar()
            if not clutch_genotype_id:
                raise SystemExit(
                    f"[STOP] missing clutch_genotypes_v11 row for clutch_id={clutch_id} (treat_code={treat_code}, dataset_key={dataset_key}); run loader_legacy_clutches first"
                )
            cx.execute(ins_tcg, {"treated_clutch_id": tclid, "clutch_genotype_id": clutch_genotype_id})

            n_tc += 1
            n_upd += cx.execute(
                upd_membership_slot,
                {"treated_clutch_id": tclid, "clutch_id": clutch_id, "slot_id": slot_id},
            ).rowcount or 0

        print(f"[OK] ensured treatments={n_treat} treated_clutches_v11_upserts={n_tc} memberships_updated={n_upd}")


if __name__ == "__main__":
    main()
