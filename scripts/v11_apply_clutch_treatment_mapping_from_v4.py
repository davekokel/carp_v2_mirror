#!/usr/bin/env python3
from __future__ import annotations

import os
import pandas as pd
from sqlalchemy import create_engine, text


def _s(x: object) -> str:
    if x is None:
        return ""
    s = str(x).strip()
    if s.lower() in ("nan", "none", "na", "n/a", "<na>"):
        return ""
    return s


def main() -> None:
    db_url = _s(os.environ.get("DB_URL"))
    if not db_url:
        raise SystemExit("[STOP] DB_URL must be set")

    map_csv = _s(os.environ.get("CLUTCH_TREAT_MAP_CSV"))
    if not map_csv:
        raise SystemExit("[STOP] CLUTCH_TREAT_MAP_CSV must be set")

    df = pd.read_csv(map_csv, dtype=str, keep_default_na=False, na_filter=False).fillna("")
    df.columns = [str(c).strip() for c in df.columns]

    need = ["clutch_code", "treat_code"]
    miss = [c for c in need if c not in df.columns]
    if miss:
        raise SystemExit(f"[STOP] mapping CSV missing columns: {miss}")

    df["clutch_code"] = df["clutch_code"].map(_s)
    df["treat_code"] = df["treat_code"].map(_s)

    df = df[df["clutch_code"].ne("") & df["treat_code"].ne("")].copy()
    if df.empty:
        print(f"[OK] nothing to apply (empty after filtering): {map_csv}")
        return

    infer_source = df.get("treatment_infer_source", "").map(_s) if "treatment_infer_source" in df.columns else ""
    infer_rule = df.get("treatment_infer_rule", "").map(_s) if "treatment_infer_rule" in df.columns else ""
    infer_batch = df.get("treatment_infer_batch_id", "").map(_s) if "treatment_infer_batch_id" in df.columns else ""

    eng = create_engine(db_url)

    # Determine whether "clutch_code" is a real clutch_code (LCL-####) or a legacy_clutch_key.
    # If any value contains '|' or starts with 'aang|'/'korra|', treat it as legacy_clutch_key.
    looks_like_key = df["clutch_code"].str.contains(r"\|", regex=True) | df["clutch_code"].str.lower().str.startswith(("aang|", "korra|"))
    using_keys = bool(looks_like_key.any())

    with eng.begin() as cx:
        # treatments lookup
        trows = cx.execute(
            text("select id::uuid as treatment_id, treat_code from public.treatments where coalesce(btrim(treat_code),'')<>''")
        ).fetchall()
        tmap = {str(tc).strip(): str(tid) for (tid, tc) in trows}

        bad_t = sorted({x for x in df["treat_code"].tolist() if x and x not in tmap})
        if bad_t:
            raise SystemExit("[STOP] some treat_code values do not exist in public.treatments. Sample:\n" + "\n".join(bad_t[:25]))

        if using_keys:
            # resolve legacy_clutch_key -> clutch_id using clutches table
            kcol = "legacy_clutch_key" if "legacy_clutch_key" in df.columns else "clutch_code"
            keys = sorted({ _s(x) for x in df[kcol].tolist() if _s(x) })
            crows = cx.execute(
                text("""
                    select id::uuid as clutch_id, legacy_clutch_key
                    from public.clutches
                    where source_system='legacy_imaging'
                      and coalesce(btrim(legacy_clutch_key),'') <> ''
                      and legacy_clutch_key = any(:keys)
                """),
                {"keys": keys},
            ).fetchall()
            cmap = {str(k).strip(): str(cid) for (cid, k) in crows}

            missing = [k for k in keys if k not in cmap]
            if missing:
                raise SystemExit("[STOP] some legacy_clutch_key values do not exist in public.clutches. Sample:\n" + "\n".join(missing[:25]))

            df["_clutch_id"] = df[kcol].map(lambda x: cmap.get(_s(x), ""))
        else:
            # resolve clutch_code -> clutch_id
            codes = sorted({ _s(x) for x in df["clutch_code"].tolist() if _s(x) })
            crows = cx.execute(
                text("""
                    select id::uuid as clutch_id, clutch_code
                    from public.clutches
                    where source_system='legacy_imaging'
                      and coalesce(btrim(clutch_code),'') <> ''
                      and clutch_code = any(:codes)
                """),
                {"codes": codes},
            ).fetchall()
            cmap = {str(cc).strip(): str(cid) for (cid, cc) in crows}

            missing = [c for c in codes if c not in cmap]
            if missing:
                raise SystemExit("[STOP] some clutch_code values do not exist in public.clutches. Sample:\n" + "\n".join(missing[:25]))

            df["_clutch_id"] = df["clutch_code"].map(lambda x: cmap.get(_s(x), ""))

        df["_treatment_id"] = df["treat_code"].map(lambda x: tmap.get(_s(x), ""))

        bad = df[df["_clutch_id"].map(_s).eq("") | df["_treatment_id"].map(_s).eq("")]
        if len(bad):
            raise SystemExit("[STOP] internal: unresolved clutch_id/treatment_id after mapping")

        payload = []
        clutch_id_col = next((c for c in ["clutch_id","_clutch_id","clutch_id_x","clutch_id_y"] if c in df.columns), None)
        treatment_id_col = next((c for c in ["treatment_id","_treatment_id","treatment_id_x","treatment_id_y"] if c in df.columns), None)
        if not clutch_id_col or not treatment_id_col:
            raise SystemExit(f"[STOP] mapping frame is missing clutch_id/treatment_id columns. cols={list(df.columns)}")

        payload = []
        for rec in df.to_dict(orient="records"):
            payload.append(
                {
                    "clutch_id": rec.get(clutch_id_col),
                    "treatment_id": rec.get(treatment_id_col),
                    "notes": "",
                    "treatment_infer_source": _s(rec.get("treatment_infer_source", "")) if "treatment_infer_source" in df.columns else "legacy_wrangling_v4_ideal",
                    "treatment_infer_rule": _s(rec.get("treatment_infer_rule", "")) if "treatment_infer_rule" in df.columns else "ideal_sheet",
                    "treatment_infer_batch_id": _s(rec.get("treatment_infer_batch_id", "")) if "treatment_infer_batch_id" in df.columns else "legacy_wrangling_v4_ideal",
                }
            )

        clutch_ids = sorted({rec.get(clutch_id_col) for rec in df.to_dict(orient="records") if rec.get(clutch_id_col)})
        if clutch_ids:
            cx.execute(
                text("delete from public.join_clutch_treatments where clutch_id = any(cast(:clutch_ids as uuid[]))"),
                {"clutch_ids": clutch_ids},
            )

        cx.execute(
            text("""
                insert into public.join_clutch_treatments (
                    id,
                    clutch_id,
                    treatment_id,
                    notes,
                    treatment_infer_source,
                    treatment_infer_rule,
                    treatment_infer_batch_id,
                    applied_at,
                    treatment_inferred_at
                )
                values (
                    gen_random_uuid(),
                    cast(:clutch_id as uuid),
                    cast(:treatment_id as uuid),
                    :notes,
                    :treatment_infer_source,
                    :treatment_infer_rule,
                    :treatment_infer_batch_id,
                    now(),
                    now()
                )
            """),
            payload,
        )
    print(f"[OK] applied clutch treatment mapping: {map_csv}")


if __name__ == "__main__":
    main()

