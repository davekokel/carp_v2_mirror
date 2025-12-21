#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import hashlib
from typing import Dict, List, Tuple

import pandas as pd
from sqlalchemy import create_engine, text

_SIG_RE = re.compile(r"plasmids=([^|]*)\|rnas=([^|]*)\|dyes=([^|]*)", re.I)
_WS_RE = re.compile(r"\s+")
_MGCO_ZERO_RE = re.compile(r"\bmgco-0+([0-9]+)\b", re.I)


def _stable_treatment_code(dataset_key: str, signature: str) -> str:
    s = (dataset_key or "").strip() + "||" + (signature or "").strip()
    h = hashlib.sha1(s.encode("utf-8")).hexdigest()[:10]
    return f"T-EXP-{h}"


def _strip_parens(s: str) -> str:
    return re.sub(r"\(.*?\)", "", s or "")


def _norm_blob(s: str) -> str:
    s = (s or "").strip().lower()
    if not s or s in ("nan", "none"):
        return ""
    s = _strip_parens(s)
    s = s.replace(";", ",").replace("|", ",")
    s = _WS_RE.sub(" ", s).strip()
    s = _MGCO_ZERO_RE.sub(r"mgco-\1", s)
    return s


def _split_codes_constructs(blob: str) -> List[str]:
    """
    For constructs only: allow whitespace as delimiter in addition to commas/pipes/semicolons.
    This prevents glued tokens like 'hc-9 lifeact:mstaygold'.
    """
    blob = _norm_blob(blob)
    if not blob:
        return []
    # Convert spaces to commas ONLY for constructs
    blob = blob.replace(" ", ",")
    parts = [p.strip() for p in blob.split(",") if p.strip()]
    out: List[str] = []
    seen = set()
    for p in parts:
        if p in seen:
            continue
        seen.add(p)
        out.append(p)
    return out


def _norm_dye_code(d: str) -> str:
    d = _norm_blob(d)
    if not d:
        return ""
    # Dyes can legitimately contain spaces (e.g., "jf 635") → normalize to hyphen
    d = d.replace(" ", "-")
    d = re.sub(r"-{2,}", "-", d)
    return d


def _split_codes_dyes(blob: str) -> List[str]:
    blob = _norm_blob(blob)
    if not blob:
        return []
    # For dyes, do NOT split on whitespace; only split on commas/pipes/semicolons already normalized above
    parts = [p.strip() for p in blob.split(",") if p.strip()]
    out: List[str] = []
    seen = set()
    for p in parts:
        if p in seen:
            continue
        seen.add(p)
        out.append(p)
    return out


def _parse_signature(sig: str) -> Tuple[List[str], List[str], List[str]]:
    m = _SIG_RE.search((sig or "").strip())
    if not m:
        return ([], [], [])
    plasmids_raw, rnas_raw, dyes_raw = m.group(1), m.group(2), m.group(3)

    plasmids = _split_codes_constructs(plasmids_raw)
    rnas = _split_codes_constructs(rnas_raw)

    dyes: List[str] = []
    dyes_raw_n = _norm_blob(dyes_raw)
    if dyes_raw_n:
        dyes = [_norm_dye_code(x) for x in _split_codes_dyes(dyes_raw_n)]
        dyes = [x for x in dyes if x]

    return (plasmids, rnas, dyes)


def _fluor_token_from_fluor_name(fluor: str) -> str:
    f = (fluor or "").strip().lower()
    if f in ("mstaygold",):
        return "msg"
    if f in ("tdmstaygold",):
        return "tdmsg"
    if f in ("halo",):
        return "halo"
    if f in ("tdmscarlet3s2", "tdmscarlet3", "mscarlet3s2", "mscarlet3"):
        return "msc3"
    if f in ("tdmchilada", "mchilada", "chilada"):
        return "mchilada"
    return ""


def _build_construct_alias_to_base(cx) -> Dict[str, str]:
    """
    Returns alias -> base_code mapping.
    Sources:
      1) explicit construct_aliases
      2) base_code itself + constructs.code/nickname/display_name
      3) synthetic aliases from v_constructs_overview.fusion_pretty, e.g.
         mStayGold-sec61b(N) => msg:sec61b (and sec61b:msg)
    """
    rows = cx.execute(
        text(
            """
            SELECT lower(c.base_code) AS base_code,
                   lower(c.code)      AS code,
                   lower(coalesce(c.nickname,''))     AS nickname,
                   lower(coalesce(c.display_name,'')) AS display_name
            FROM public.constructs c;
            """
        )
    ).fetchall()

    alias_rows = cx.execute(
        text(
            """
            SELECT lower(a.alias) AS alias, lower(c.base_code) AS base_code
            FROM public.construct_aliases a
            JOIN public.constructs c ON c.id = a.construct_id;
            """
        )
    ).fetchall()

    vc = cx.execute(
        text(
            """
            SELECT lower(construct_code) AS construct_code,
                   lower(coalesce(fusion_pretty,'')) AS fusion_pretty
            FROM public.v_constructs_overview;
            """
        )
    ).fetchall()

    base_by_code: Dict[str, str] = {}
    for base_code, code, nickname, display_name in rows:
        bc = (base_code or "").strip()
        if not bc:
            continue
        for k in (bc, code, nickname, display_name):
            k = (k or "").strip()
            if k:
                base_by_code[k] = bc

    alias_to_base: Dict[str, str] = {}

    for alias, base_code in alias_rows:
        a = (alias or "").strip()
        b = (base_code or "").strip()
        if a and b:
            alias_to_base[a] = b

    for k, bc in base_by_code.items():
        alias_to_base[k] = bc

    fp_re = re.compile(r"^(?P<fluor>[a-z0-9]+)-(?P<target>[^()]+)\(", re.I)
    for construct_code, fusion_pretty in vc:
        cc = (construct_code or "").strip()
        fp = (fusion_pretty or "").strip()
        if not cc or not fp:
            continue
        bc = base_by_code.get(cc)
        if not bc:
            continue

        m = fp_re.match(fp)
        if not m:
            continue

        fluor = m.group("fluor")
        target = m.group("target")
        fluor_tok = _fluor_token_from_fluor_name(fluor)
        if not fluor_tok:
            continue

        target_tok = _norm_blob(target).replace(" ", "").replace("-", "").replace("_", "")
        if not target_tok:
            continue

        a1 = f"{fluor_tok}:{target_tok}"
        alias_to_base[a1] = bc

        a2 = f"{target_tok}:{fluor_tok}"
        alias_to_base[a2] = bc

    return alias_to_base


def _rewrite_colon_fluor_tokens(token: str) -> str:
    """
    Normalize colon tokens so they match synthetic aliases:
      lifeact:mstaygold -> lifeact:msg
      mstaygold:sec61b  -> msg:sec61b
    """
    t = (token or "").strip().lower()
    if ":" not in t:
        return t
    a, b = t.split(":", 1)
    a = a.strip()
    b = b.strip()

    repl = {
        "mstaygold": "msg",
        "tdmstaygold": "tdmsg",
        "tdmscarlet3s2": "msc3",
        "tdmscarlet3": "msc3",
        "mscarlet3s2": "msc3",
        "mscarlet3": "msc3",
        "tdmchilada": "mchilada",
        "chilada": "mchilada",
    }

    a2 = repl.get(a, a)
    b2 = repl.get(b, b)

    # normalize mgco-01 -> mgco-1 if present inside tokens (rare, but safe)
    a2 = _MGCO_ZERO_RE.sub(r"mgco-\1", a2)
    b2 = _MGCO_ZERO_RE.sub(r"mgco-\1", b2)

    return f"{a2}:{b2}"


def _resolve_construct_base_code(code: str, alias_to_base: Dict[str, str]) -> str:
    c_raw = _norm_blob(code)
    if not c_raw:
        return ""

    # keep colon structure when present; otherwise strip punctuation aggressively
    if ":" in c_raw:
        c = _rewrite_colon_fluor_tokens(c_raw).replace(" ", "")
        c = _MGCO_ZERO_RE.sub(r"mgco-\1", c)
    else:
        c = c_raw.replace(" ", "").replace("_", "")
        c = _MGCO_ZERO_RE.sub(r"mgco-\1", c)

    if c in alias_to_base:
        return alias_to_base[c]

    c2 = re.sub(r"[^a-z0-9:]+", "", c)
    if c2 in alias_to_base:
        return alias_to_base[c2]

    raise SystemExit(f"[STOP] unknown construct token/base_code {code!r} (normalized={c!r})")


def _ensure_treatment_mix_and_ingredients(cx, treatment_id: str, sig: str, alias_to_base: Dict[str, str]) -> None:
    mix_id = cx.execute(
        text(
            """
            INSERT INTO public.treatment_mixes (treatment_id, mix_code, notes, created_at)
            VALUES (:treatment_id, 'M1', 'auto: v11_apply_exp_treatment_signatures_csv', now())
            ON CONFLICT (treatment_id, mix_code)
            DO UPDATE SET notes = EXCLUDED.notes
            RETURNING id::text;
            """
        ),
        {"treatment_id": treatment_id},
    ).scalar()

    if not mix_id:
        mix_id = cx.execute(
            text(
                """
                SELECT id::text
                FROM public.treatment_mixes
                WHERE treatment_id = :treatment_id AND mix_code = 'M1'
                LIMIT 1;
                """
            ),
            {"treatment_id": treatment_id},
        ).scalar()

    if not mix_id:
        raise SystemExit(f"[STOP] failed to ensure treatment_mixes(M1) for treatment_id={treatment_id}")

    plasmids_raw, rnas_raw, dyes_raw = _parse_signature(sig)

    def insert_constructs(raw_codes: List[str], delivery_form: str) -> None:
        for raw in raw_codes:
            base_code = _resolve_construct_base_code(raw, alias_to_base)
            cid = cx.execute(
                text(
                    """
                    SELECT id::text
                    FROM public.constructs
                    WHERE lower(base_code) = :c
                    LIMIT 1;
                    """
                ),
                {"c": base_code},
            ).scalar()
            if not cid:
                raise SystemExit(f"[STOP] resolved {raw!r} -> {base_code!r} but construct row missing")

            cx.execute(
                text(
                    """
                    INSERT INTO public.treatment_mix_constructs (mix_id, construct_id, delivery_form)
                    VALUES (:mix_id, :construct_id, :delivery_form)
                    ON CONFLICT DO NOTHING;
                    """
                ),
                {"mix_id": mix_id, "construct_id": cid, "delivery_form": delivery_form},
            )

    insert_constructs(plasmids_raw, "plasmid")
    insert_constructs(rnas_raw, "rna")

    # DYES (strict but normalization-aware: match alnum-only keys across code/display_name/nickname)
    for raw in dyes_raw:
        code = _norm_dye_code(raw)
        if not code:
            continue

        key = "".join(ch for ch in code.lower() if ch.isalnum())
        if not key:
            continue

        rows = cx.execute(
            text(
                """
                SELECT id::text
                FROM public.dyes
                WHERE regexp_replace(lower(btrim(code)), '[^a-z0-9]+', '', 'g') = :k
                   OR regexp_replace(lower(btrim(display_name)), '[^a-z0-9]+', '', 'g') = :k
                   OR regexp_replace(lower(btrim(nickname)), '[^a-z0-9]+', '', 'g') = :k
                """
            ),
            {"k": key},
        ).fetchall()

        ids = sorted({r[0] for r in rows if r and r[0]})
        if len(ids) == 0:
            raise SystemExit(f"[STOP] unknown dye code {code!r} (raw={raw!r}, treatment_id={treatment_id})")
        if len(ids) > 1:
            raise SystemExit(f"[STOP] ambiguous dye code {code!r} matched multiple dye ids {ids} (raw={raw!r}, treatment_id={treatment_id})")

        cx.execute(
            text(
                """
                INSERT INTO public.treatment_mix_dyes (mix_id, dye_id)
                VALUES (:mix_id, :dye_id)
                ON CONFLICT DO NOTHING
                """
            ),
            {"mix_id": mix_id, "dye_id": ids[0]},
        )


def main() -> None:
    db_url = os.environ.get("DB_URL")
    if not db_url:
        raise SystemExit("[STOP] DB_URL is not set")

    csv_auto = "seed_kits/legacy_wrangling_v3/working/exp_treatment_signatures.csv"
    csv_override = "seed_kits/legacy_wrangling_v3/working/exp_treatment_manual_overrides.csv"

    df_auto = pd.read_csv(csv_auto, low_memory=False)
    df_auto["source"] = "auto"

    try:
        df_ovr = pd.read_csv(csv_override, low_memory=False)
        df_ovr["source"] = "override"
    except FileNotFoundError:
        df_ovr = pd.DataFrame(columns=["bruker_roi_id", "dataset_key", "signature", "source"])

    df = pd.concat([df_auto, df_ovr], ignore_index=True)

    for c in ("bruker_roi_id", "dataset_key", "signature"):
        if c not in df.columns:
            raise SystemExit(f"[STOP] combined mapping missing column {c!r}; found {list(df.columns)}")

    df["bruker_roi_id"] = df["bruker_roi_id"].astype(str).str.strip()
    df["dataset_key"] = df["dataset_key"].astype(str).str.strip()
    df["signature"] = df["signature"].astype(str).str.strip()

    df = df.dropna(subset=["bruker_roi_id", "dataset_key", "signature"])
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
        alias_to_base = _build_construct_alias_to_base(cx)

        df_map = pd.read_sql(
            text(
                """
                SELECT ra.roi_code, icm.clutch_id::text AS clutch_id
                FROM public.imaging_roi_annotations ra
                JOIN public.imaging_clutch_memberships icm ON icm.slot_id = ra.slot_id
                """
            ),
            cx,
        )
        df_map["roi_code"] = df_map["roi_code"].astype(str).str.strip()

        df2 = df.merge(df_map, left_on="bruker_roi_id", right_on="roi_code", how="inner")
        if df2.empty:
            raise SystemExit("[STOP] No rows matched DB roi_code (bruker_roi_id ↔ imaging_roi_annotations.roi_code)")

        df_cl = pd.read_sql(text("SELECT id::text AS clutch_id, clutch_code FROM public.clutches"), cx)
        clutch_id_to_code = dict(zip(df_cl["clutch_id"].astype(str), df_cl["clutch_code"].astype(str)))

        df2["treatment_code"] = df2.apply(
            lambda r: _stable_treatment_code(str(r["dataset_key"]), str(r["signature"])),
            axis=1,
        )

        ins_treat = text(
            """
            INSERT INTO public.treatments (id, kind_code, treat_code, treat_text, created_at)
            VALUES (gen_random_uuid(), 'legacy', :treat_code, :treat_text, now())
            ON CONFLICT (treat_code) DO UPDATE
              SET treat_text = EXCLUDED.treat_text
            RETURNING id::text AS treatment_id;
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
            RETURNING id::text AS treated_clutch_id;
            """
        )

        upd_m = text(
            """
            UPDATE public.imaging_clutch_memberships
            SET treated_clutch_id = :treated_clutch_id
            WHERE clutch_id = :clutch_id;
            """
        )

        pairs = df2[["clutch_id", "treatment_code", "dataset_key", "signature"]].drop_duplicates().reset_index(drop=True)

        n_treat = 0
        n_tc = 0
        n_upd = 0
        treat_code_to_id: Dict[str, str] = {}

        for _, r in pairs.iterrows():
            clutch_id = str(r["clutch_id"])
            tcode = str(r["treatment_code"])
            dataset_key = str(r["dataset_key"])
            sig = str(r["signature"])

            if clutch_id not in clutch_id_to_code:
                raise SystemExit(f"[STOP] clutch_id not found in public.clutches: {clutch_id}")

            if tcode not in treat_code_to_id:
                tid = cx.execute(ins_treat, {"treat_code": tcode, "treat_text": f"{dataset_key} :: {sig}"}).scalar()
                if not tid:
                    raise SystemExit(f"[STOP] failed to upsert treatments for {tcode}")
                treat_code_to_id[tcode] = tid
                n_treat += 1

            treatment_id = treat_code_to_id[tcode]

            # Ensure mix + ingredients exist (strict resolution; no silent fallback)
            _ensure_treatment_mix_and_ingredients(cx, treatment_id, sig, alias_to_base)

            clutch_code = clutch_id_to_code[clutch_id]
            base = clutch_code.replace("LCL-", "TCL-", 1) if clutch_code.startswith("LCL-") else f"TCL-{clutch_code}"
            treated_code = f"{base}-{tcode[-6:]}"
            notes = f"{dataset_key} :: {sig}"

            tclid = cx.execute(
                ins_tc,
                {"clutch_id": clutch_id, "treated_clutch_code": treated_code, "treatment_id": treatment_id, "notes": notes},
            ).scalar()
            if not tclid:
                raise SystemExit(f"[STOP] failed to upsert treated_clutches_v11 for clutch_id={clutch_id} tcode={tcode}")

            n_tc += 1
            n_upd += cx.execute(upd_m, {"treated_clutch_id": tclid, "clutch_id": clutch_id}).rowcount or 0

        print(f"[OK] ensured treatments={n_treat} treated_clutches_v11_upserts={n_tc} memberships_updated={n_upd}")


if __name__ == "__main__":
    main()