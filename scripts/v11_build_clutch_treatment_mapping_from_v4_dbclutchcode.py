#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import pandas as pd
from sqlalchemy import create_engine, text


EMPTY_SIG = "plasmids=|rnas=|dyes="


def _s(x: object) -> str:
    if x is None:
        return ""
    s = str(x).strip()
    if s.lower() in ("nan", "none", "na", "n/a", "<na>"):
        return ""
    return s


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ideal-tsv", required=True)
    ap.add_argument("--out-csv", required=True)
    args = ap.parse_args()

    db_url = _s(os.environ.get("DB_URL"))
    if not db_url:
        raise SystemExit("[STOP] DB_URL must be set")

    df = pd.read_csv(args.ideal_tsv, sep="\t", dtype=str, keep_default_na=False, na_filter=False).fillna("")
    df.columns = [str(c).strip() for c in df.columns]

    need = ["roi_path", "treat_code", "signature_text"]
    miss = [c for c in need if c not in df.columns]
    if miss:
        raise SystemExit(f"[STOP] ideal TSV missing columns: {miss}")

    if "include_in_db" in df.columns:
        inc = df["include_in_db"].astype(str).str.strip().str.lower().isin(["1", "t", "true", "y", "yes"])
        df = df[inc].copy()

    df["roi_path"] = df["roi_path"].map(_s)
    df["treat_code"] = df["treat_code"].map(_s)
    df["signature_text"] = df["signature_text"].map(_s)

    df = df[df["roi_path"].ne("")].copy()
    df = df[df["treat_code"].ne("")].copy()
    df = df[df["signature_text"].ne("") & df["signature_text"].ne(EMPTY_SIG)].copy()

    if df.empty:
        pd.DataFrame(
            columns=[
                "clutch_code",
                "treat_code",
                "treat_text",
                "n_rois",
                "treatment_infer_source",
                "treatment_infer_rule",
                "treatment_infer_batch_id",
            ]
        ).to_csv(args.out_csv, index=False)
        print(args.out_csv)
        return

    eng = create_engine(db_url)
    roi_paths = df["roi_path"].tolist()

    with eng.begin() as cx:
        rows = cx.execute(
            text(
                """
                select
                  ira.roi_path,
                  c.clutch_code
                from public.imaging_roi_annotations ira
                join public.imaging_clutch_memberships m on m.slot_id = ira.slot_id
                join public.clutches c on c.id = m.clutch_id
                where ira.roi_path = any(:paths)
                """
            ),
            {"paths": roi_paths},
        ).fetchall()

    map_df = pd.DataFrame(rows, columns=["roi_path", "clutch_code"])
    map_df["roi_path"] = map_df["roi_path"].map(_s)
    map_df["clutch_code"] = map_df["clutch_code"].map(_s)
    map_df = map_df[map_df["roi_path"].ne("") & map_df["clutch_code"].ne("")].drop_duplicates()

    m = df.merge(map_df, on="roi_path", how="left", validate="m:1")
    unmapped = m["clutch_code"].map(_s).eq("")
    if int(unmapped.sum()):
        sample = m.loc[unmapped, ["roi_path"]].head(25).to_string(index=False)
        raise SystemExit("[STOP] some roi_path did not map to clutch_code in DB. Sample:\n" + sample)

    per = (
        m.groupby("clutch_code", as_index=False)
        .agg(
            n_rois=("roi_path", "size"),
            n_treat_codes=("treat_code", lambda s: len({x for x in s.astype(str).map(_s).tolist() if x})),
            treat_code=("treat_code", lambda s: ";".join(sorted({x for x in s.astype(str).map(_s).tolist() if x}))),
            treat_text=("signature_text", lambda s: ";".join(sorted({x for x in s.astype(str).map(_s).tolist() if x}))),
        )
        .copy()
    )

    multi = per[per["n_treat_codes"].astype(int) != 1].copy()
    if len(multi):
        print(multi.sort_values(["n_treat_codes", "clutch_code"], ascending=[False, True]).head(200).to_string(index=False))
        raise SystemExit("[STOP] clutches with !=1 treatment signature; fix upstream (ideal rules)")

    out = per[["clutch_code", "treat_code", "treat_text", "n_rois"]].copy()
    out["treatment_infer_source"] = "legacy_wrangling_v4_ideal"
    out["treatment_infer_rule"] = "ideal_sheet:roi_path->db clutch_code + treatment signature"
    out["treatment_infer_batch_id"] = "legacy_wrangling_v4_ideal"

    out.to_csv(args.out_csv, index=False)
    print(args.out_csv)


if __name__ == "__main__":
    main()
