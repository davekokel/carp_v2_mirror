from __future__ import annotations

import os
import hashlib
from typing import Dict, List, Tuple

import pandas as pd
from sqlalchemy import create_engine, text

CSV_DEFAULT = "seed_kits/legacy_wrangling_v4/working/legacy_imaging_annotations_for_db_v9.csv"

INFER_SOURCE = "free_text_label"
INFER_RULE = "v11_apply_free_text_label_treatments"
BATCH_ID = "legacy_free_text_label_v4"


def _s(x) -> str:
    if x is None:
        return ""
    s = str(x).strip()
    if s.lower() in ("nan", "none", "na", "n/a", "<na>"):
        return ""
    return s


def _treat_code_for_label(label: str) -> str:
    h = hashlib.sha1(label.encode("utf-8")).hexdigest()[:10]
    return f"T-LABEL-{h}"


def main() -> None:
    db_url = os.environ.get("DB_URL")
    if not db_url:
        raise SystemExit("[STOP] DB_URL is not set")

    csv_path = os.environ.get("FREE_TEXT_LABEL_CSV", CSV_DEFAULT)
    df = pd.read_csv(csv_path, low_memory=False)
    df.columns = [str(c).strip() for c in df.columns]

    if "roi_dir" not in df.columns:
        raise SystemExit(f"[STOP] {csv_path} missing roi_dir")
    if "free_text_label" not in df.columns:
        print(f"[OK] {csv_path} has no free_text_label column; nothing to do.")
        return

    df["roi_path"] = df["roi_dir"].astype(str).map(_s)
    df["free_text_label"] = df["free_text_label"].astype(str).map(_s)
    df = df[(df["roi_path"] != "") & (df["free_text_label"] != "")].copy()

    if df.empty:
        print("[OK] no nonblank free_text_label rows; nothing to do.")
        return

    roi_paths = sorted(df["roi_path"].unique().tolist())

    engine = create_engine(db_url)

    with engine.begin() as cx:
        # roi_path -> clutch_id, clutch_code
        rows = cx.execute(
            text(
                """
                SELECT
                  ira.roi_path,
                  c.id::text AS clutch_id,
                  c.clutch_code
                FROM public.imaging_roi_annotations ira
                JOIN public.imaging_clutch_memberships m ON m.slot_id = ira.slot_id
                JOIN public.clutches c ON c.id = m.clutch_id
                WHERE ira.roi_path = ANY(:paths)
                """
            ),
            {"paths": roi_paths},
        ).fetchall()

        if not rows:
            raise SystemExit("[STOP] no roi_path matched DB imaging_roi_annotations")

        path2clutch: Dict[str, Tuple[str, str]] = {r[0]: (r[1], r[2]) for r in rows}

        df["clutch_id"] = df["roi_path"].map(lambda p: path2clutch.get(p, ("", ""))[0])
        df["clutch_code"] = df["roi_path"].map(lambda p: path2clutch.get(p, ("", ""))[1])
        df = df[(df["clutch_id"] != "") & (df["clutch_code"] != "")].copy()

        if df.empty:
            raise SystemExit("[STOP] no free_text_label rows mapped to clutch_id")

        # Only attach label-treatments to clutches that currently have zero join_clutch_treatments
        clutches = sorted(df["clutch_id"].unique().tolist())

        existing = cx.execute(
            text(
                """
                SELECT j.clutch_id::text AS clutch_id, count(*) AS n
                FROM public.join_clutch_treatments j
                WHERE j.clutch_id IN (
                  SELECT CAST(x AS uuid)
                  FROM unnest(:cids) AS x
                )
                GROUP BY 1
                """
            ),
            {"cids": clutches},
        ).fetchall()

        n_by_clutch = {r[0]: int(r[1]) for r in existing}
        df["n_join_existing"] = df["clutch_id"].map(lambda cid: n_by_clutch.get(cid, 0))
        before = len(df)
        df = df[df["n_join_existing"].astype(int).eq(0)].copy()

        print(f"[INFO] free_text_label rows in CSV: {before}")
        print(f"[INFO] eligible rows after skip(clutch has join_clutch_treatments): {len(df)}")

        if df.empty:
            print("[OK] all candidate clutches already have join_clutch_treatments; nothing to do.")
            return

        # Build unique clutch_id -> label (if multiple labels per clutch, keep first deterministically)
        df = df.sort_values(["clutch_code", "free_text_label", "roi_path"])
        clutch_label = df.drop_duplicates(subset=["clutch_id"], keep="first")[["clutch_id", "free_text_label"]].copy()

        clutch_label["treat_code"] = clutch_label["free_text_label"].map(_treat_code_for_label)
        clutch_label["treat_text"] = clutch_label["free_text_label"].map(lambda x: f"label({x})")

        # Upsert treatments
        treat_rows = clutch_label[["treat_code", "treat_text"]].drop_duplicates().to_dict("records")
        if treat_rows:
            cx.execute(text("CREATE TEMP TABLE _tmp_label_treats (treat_code text, treat_text text) ON COMMIT DROP"))
            cx.execute(
                text("INSERT INTO _tmp_label_treats (treat_code, treat_text) VALUES (:treat_code, :treat_text)"),
                treat_rows,
            )
            cx.execute(
                text(
                    """
                    INSERT INTO public.treatments (id, treat_code, kind_code, treat_text, created_at)
                    SELECT gen_random_uuid(), t.treat_code, 'injection_mix', t.treat_text, now()
                    FROM _tmp_label_treats t
                    ON CONFLICT (treat_code) DO UPDATE
                    SET treat_text = EXCLUDED.treat_text;
                    """
                )
            )

        # Resolve treatment_id
        treat_codes = sorted(clutch_label["treat_code"].unique().tolist())
        tdf = pd.read_sql(
            text(
                """
                SELECT treat_code, id::text AS treatment_id
                FROM public.treatments
                WHERE treat_code = ANY(:codes)
                """
            ),
            cx,
            params={"codes": treat_codes},
        )
        tmap = dict(zip(tdf["treat_code"].astype(str), tdf["treatment_id"].astype(str)))
        clutch_label["treatment_id"] = clutch_label["treat_code"].map(lambda tc: tmap.get(tc, ""))

        missing_tid = int((clutch_label["treatment_id"].astype(str).str.strip() == "").sum())
        if missing_tid:
            raise SystemExit(f"[STOP] {missing_tid} treat_code values failed to resolve treatment_id")

        # Insert join_clutch_treatments with provenance (skip if already exists)
        links = clutch_label[["clutch_id", "treatment_id"]].drop_duplicates().to_dict("records")

        cx.execute(text("CREATE TEMP TABLE _tmp_links (clutch_id uuid, treatment_id uuid) ON COMMIT DROP"))
        cx.execute(
            text("INSERT INTO _tmp_links (clutch_id, treatment_id) VALUES (:clutch_id, :treatment_id)"),
            links,
        )

        res = cx.execute(
            text(
                """
                INSERT INTO public.join_clutch_treatments
                  (id, clutch_id, treatment_id, applied_at, created_at, notes,
                   treatment_infer_source, treatment_infer_rule, treatment_infer_batch_id, treatment_inferred_at)
                SELECT
                  gen_random_uuid(),
                  tl.clutch_id,
                  tl.treatment_id,
                  now(),
                  now(),
                  'free_text_label',
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
                """
            ),
            {"src": INFER_SOURCE, "rule": INFER_RULE, "batch": BATCH_ID},
        )

        print(f"[OK] upserted treatments={len(treat_rows)}")
        print(f"[OK] inserted join_clutch_treatments={int(res.rowcount or 0)}")


if __name__ == "__main__":
    main()
