from __future__ import annotations

import os
from collections import defaultdict
from typing import Dict, Set, Tuple

import pandas as pd
from sqlalchemy import create_engine, text

CSV = "seed_kits/legacy_wrangling_v3/working/exp_treatment_signatures.csv"

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

    # Normalize columns
    for c in ("bruker_roi_id", "dataset_key", "signature"):
        if c not in df.columns:
            raise SystemExit(f"[STOP] combined mapping missing column {c!r}; found {list(df.columns)}")

    df["bruker_roi_id"] = df["bruker_roi_id"].astype(str).str.strip()
    df["dataset_key"] = df["dataset_key"].astype(str).str.strip()
    df["signature"] = df["signature"].astype(str).str.strip()

    # Overrides take precedence: keep last occurrence per (dataset_key, bruker_roi_id)
    df = df.dropna(subset=["bruker_roi_id", "dataset_key", "signature"])
    df = df.sort_values(["dataset_key", "bruker_roi_id", "source"]).drop_duplicates(
        subset=["dataset_key", "bruker_roi_id"],
        keep="last",
    ).reset_index(drop=True)
    for c in ("bruker_roi_id","dataset_key","signature"):
        if c not in df.columns:
            raise SystemExit(f"[STOP] {CSV} missing column {c!r}; found {list(df.columns)}")

    df["bruker_roi_id"] = df["bruker_roi_id"].astype(str).str.strip()
    df["dataset_key"] = df["dataset_key"].astype(str).str.strip()
    df["signature"] = df["signature"].astype(str).str.strip()

    # Deterministic: each (dataset_key, bruker_roi_id) must map to exactly 1 signature
    bad = df.groupby(["dataset_key","bruker_roi_id"])["signature"].nunique()
    bad = bad[bad > 1]
    if not bad.empty:
        raise SystemExit(f"[STOP] ambiguous signatures per ROI (first 10): {bad.head(10).to_dict()}")

    eng = create_engine(db_url)

    with eng.begin() as cx:
        # Map roi_code -> clutch_id via DB
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
            raise SystemExit("[STOP] No rows in exp_treatment_signatures.csv matched DB roi_code")

        # Map clutch_id -> clutch_code
        df_cl = pd.read_sql(text("SELECT id::text AS clutch_id, clutch_code FROM public.clutches"), cx)
        clutch_id_to_code = dict(zip(df_cl["clutch_id"].astype(str), df_cl["clutch_code"].astype(str)))

        # Build treatment_code deterministically from (dataset_key, signature)
        # (stable + reproducible; no guessing)
        df2["treatment_code"] = df2.apply(
            lambda r: "T-EXP-" + str(abs(hash((r["dataset_key"], r["signature"]))) % (10**10)).zfill(10),
            axis=1
        )

        # Ensure treatments exist (one per treatment_code)
        # Store signature as treat_text for traceability
        ins_treat = text(
            """
            INSERT INTO public.treatments (id, kind_code, treat_code, treat_text, created_at)
            VALUES (gen_random_uuid(), 'legacy', :treat_code, :treat_text, now())
            ON CONFLICT (treat_code) DO UPDATE
              SET treat_text = EXCLUDED.treat_text
            RETURNING id::text AS treatment_id;
            """
        )

        # Upsert treated_clutches_v11 and update memberships
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

        # Group by clutch_id + treatment_code (a clutch can have multiple treatments across experiments)
        pairs = df2[["clutch_id","treatment_code","dataset_key","signature"]].drop_duplicates().reset_index(drop=True)

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
            clutch_code = clutch_id_to_code[clutch_id]
            base = clutch_code.replace("LCL-", "TCL-", 1) if clutch_code.startswith("LCL-") else f"TCL-{clutch_code}"
            treated_code = f"{base}-{tcode[-6:]}"
            notes = f"{dataset_key} :: {sig}"

            tclid = cx.execute(ins_tc, {"clutch_id": clutch_id, "treated_clutch_code": treated_code, "treatment_id": treatment_id, "notes": notes}).scalar()
            if not tclid:
                raise SystemExit(f"[STOP] failed to upsert treated_clutches_v11 for clutch_id={clutch_id} tcode={tcode}")
            n_tc += 1
            n_upd += cx.execute(upd_m, {"treated_clutch_id": tclid, "clutch_id": clutch_id}).rowcount or 0

        print(f"[OK] ensured treatments={n_treat} treated_clutches_v11_upserts={n_tc} memberships_updated={n_upd}")

if __name__ == "__main__":
    main()
