from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pandas as pd
from sqlalchemy import create_engine, text


def _s(x: object) -> str:
    if x is None:
        return ""
    s = str(x).strip()
    if s.lower() in ("nan", "none", "na", "n/a", "<na>"):
        return ""
    return s


def _qc_dir(map_csv: str) -> Path:
    p = Path(map_csv).resolve()
    root = p.parents[3] if "seed_kits" in p.parts else Path.cwd()
    out = root / "seed_kits" / "legacy_wrangling_v4" / "working" / "qc_runs"
    out.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    d = out / f"v11_apply_clutch_treat_map__{run_id}"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _ensure_treatments(cx, df: pd.DataFrame, qc: Dict[str, Any]) -> Dict[str, str]:
    trows = cx.execute(
        text("select id::uuid as treatment_id, treat_code from public.treatments where coalesce(btrim(treat_code),'')<>''")
    ).fetchall()
    tmap = {str(tc).strip(): str(tid) for (tid, tc) in trows}

    missing_codes = sorted({x for x in df["treat_code"].tolist() if x and x not in tmap})
    qc["n_treat_codes_missing_pre_ensure"] = len(missing_codes)

    if not missing_codes:
        qc["n_treat_codes_ensured_inserted"] = 0
        return tmap

    treat_text_by_code: Dict[str, str] = {}
    if "treat_text" in df.columns:
        for r in df[["treat_code", "treat_text"]].to_dict(orient="records"):
            treat_text_by_code[_s(r.get("treat_code"))] = _s(r.get("treat_text"))

    batch_by_code: Dict[str, str] = {}
    if "treatment_infer_batch_id" in df.columns:
        for r in df[["treat_code", "treatment_infer_batch_id"]].to_dict(orient="records"):
            batch_by_code[_s(r.get("treat_code"))] = _s(r.get("treatment_infer_batch_id"))

    payload: List[Dict[str, Any]] = []
    for code in missing_codes:
        payload.append(
            {
                "treat_code": code,
                "treat_text": treat_text_by_code.get(code, "") or code,
                "import_batch_id": batch_by_code.get(code, "") or "legacy_wrangling_v4_ideal",
            }
        )

    cx.execute(
        text(
            """
            insert into public.treatments (
                id, treat_code, kind_code, treat_text, notes, source_system, import_batch_id, created_at
            )
            values (
                gen_random_uuid(),
                :treat_code,
                'legacy',
                nullif(btrim(:treat_text),''),
                '',
                'legacy_imaging',
                nullif(btrim(:import_batch_id),''),
                now()
            )
            on conflict (treat_code) do nothing
            """
        ),
        payload,
    )

    trows2 = cx.execute(
        text("select id::uuid as treatment_id, treat_code from public.treatments where coalesce(btrim(treat_code),'')<>''")
    ).fetchall()
    tmap2 = {str(tc).strip(): str(tid) for (tid, tc) in trows2}

    still_missing = sorted({x for x in df["treat_code"].tolist() if x and x not in tmap2})
    qc["n_treat_codes_missing_post_ensure"] = len(still_missing)
    qc["n_treat_codes_ensured_inserted"] = len(missing_codes) - len(still_missing)

    if still_missing:
        raise SystemExit("[STOP] treat_code still missing after ensure. Sample:\n" + "\n".join(still_missing[:25]))

    return tmap2


def _resolve_clutches(cx, df: pd.DataFrame, qc: Dict[str, Any]) -> Tuple[pd.DataFrame, List[str]]:
    looks_like_key = df["clutch_code"].str.contains(r"\|", regex=True) | df["clutch_code"].str.lower().str.startswith(("aang|", "korra|"))
    using_keys = bool(looks_like_key.any())
    qc["using_legacy_keys_mode"] = using_keys

    if using_keys:
        kcol = "legacy_clutch_key" if "legacy_clutch_key" in df.columns else "clutch_code"
        keys = sorted({_s(x) for x in df[kcol].tolist() if _s(x)})
        crows = cx.execute(
            text(
                """
                select id::uuid as clutch_id, legacy_clutch_key
                from public.clutches
                where coalesce(btrim(legacy_clutch_key),'') <> ''
                  and legacy_clutch_key = any(:keys)
                """
            ),
            {"keys": keys},
        ).fetchall()
        cmap = {str(k).strip(): str(cid) for (cid, k) in crows}

        df = df.copy()
        df["_clutch_id"] = df[kcol].map(lambda x: cmap.get(_s(x), ""))

        missing_keys = sorted({k for k in keys if k not in cmap})
        qc["n_mapping_rows_missing_clutch"] = int(df["_clutch_id"].map(_s).eq("").sum())
        qc["n_missing_clutch_keys_distinct"] = len(missing_keys)

        return df, missing_keys

    codes = sorted({_s(x) for x in df["clutch_code"].tolist() if _s(x)})
    crows = cx.execute(
        text(
            """
            select id::uuid as clutch_id, clutch_code
            from public.clutches
            where coalesce(btrim(clutch_code),'') <> ''
              and clutch_code = any(:codes)
            """
        ),
        {"codes": codes},
    ).fetchall()
    cmap = {str(cc).strip(): str(cid) for (cid, cc) in crows}

    df = df.copy()
    df["_clutch_id"] = df["clutch_code"].map(lambda x: cmap.get(_s(x), ""))

    missing_codes = sorted({c for c in codes if c not in cmap})
    qc["n_mapping_rows_missing_clutch"] = int(df["_clutch_id"].map(_s).eq("").sum())
    qc["n_missing_clutch_codes_distinct"] = len(missing_codes)

    return df, missing_codes


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

    qc: Dict[str, Any] = {
        "map_csv": str(Path(map_csv).resolve()),
        "n_mapping_rows_input": int(len(df)),
    }
    qcdir = _qc_dir(map_csv)

    eng = create_engine(db_url)

    with eng.begin() as cx:
        tmap = _ensure_treatments(cx, df, qc)

        df2, missing_clutches = _resolve_clutches(cx, df, qc)
        df2["_treatment_id"] = df2["treat_code"].map(lambda x: tmap.get(_s(x), ""))

        bad_t = df2["_treatment_id"].map(_s).eq("")
        if int(bad_t.sum()):
            raise SystemExit("[STOP] internal: unresolved treatment_id after ensure")

        skip_mask = df2["_clutch_id"].map(_s).eq("")
        qc["n_mapping_rows_skipped_missing_clutch"] = int(skip_mask.sum())
        qc["n_mapping_rows_to_apply"] = int((~skip_mask).sum())

        if qc["n_mapping_rows_skipped_missing_clutch"]:
            sample = df2.loc[skip_mask, ["clutch_code", "treat_code"]].head(50)
            sample.to_csv(qcdir / "skipped_missing_clutches_sample.csv", index=False)

        apply_df = df2.loc[~skip_mask].copy()
        if apply_df.empty:
            Path(qcdir / "qc.json").write_text(pd.Series(qc).to_json(), encoding="utf-8")
            print(f"[OK] nothing to apply (all mappings missing clutches). qc_dir={qcdir}")
            return

        payload: List[Dict[str, Any]] = []
        for rec in apply_df.to_dict(orient="records"):
            payload.append(
                {
                    "clutch_id": rec.get("_clutch_id"),
                    "treatment_id": rec.get("_treatment_id"),
                    "notes": "",
                    "treatment_infer_source": _s(rec.get("treatment_infer_source", "")) if "treatment_infer_source" in apply_df.columns else "legacy_wrangling_v4_ideal",
                    "treatment_infer_rule": _s(rec.get("treatment_infer_rule", "")) if "treatment_infer_rule" in apply_df.columns else "ideal_sheet",
                    "treatment_infer_batch_id": _s(rec.get("treatment_infer_batch_id", "")) if "treatment_infer_batch_id" in apply_df.columns else "legacy_wrangling_v4_ideal",
                }
            )

        clutch_ids = sorted({rec["clutch_id"] for rec in payload if rec.get("clutch_id")})
        cx.execute(
            text("delete from public.join_clutch_treatments where clutch_id = any(cast(:clutch_ids as uuid[]))"),
            {"clutch_ids": clutch_ids},
        )

        cx.execute(
            text(
                """
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
                """
            ),
            payload,
        )

    (qcdir / "qc.json").write_text(pd.Series(qc).to_json(), encoding="utf-8")
    pd.DataFrame([qc]).to_csv(qcdir / "qc.csv", index=False)

    print(f"[OK] applied clutch treatment mapping: {map_csv}")
    print(f"[QC] qc_dir={qcdir}")
    print(f"[QC] ensured_missing_treatments_inserted={qc.get('n_treat_codes_ensured_inserted', 0)}")
    print(f"[QC] skipped_missing_clutches={qc.get('n_mapping_rows_skipped_missing_clutch', 0)}")
    print(f"[QC] applied_rows={qc.get('n_mapping_rows_to_apply', 0)}")


if __name__ == "__main__":
    main()
