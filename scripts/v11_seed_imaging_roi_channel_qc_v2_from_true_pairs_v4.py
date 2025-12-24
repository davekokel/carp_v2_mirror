from __future__ import annotations

import os
from pathlib import Path
import pandas as pd
from sqlalchemy import create_engine, text

PAIR_TSV = Path("seed_kits/legacy_wrangling_v4/working/roi_channel_pairs_true.tsv")

def main() -> None:
    db_url = os.environ.get("DB_URL")
    if not db_url:
        raise SystemExit("[STOP] DB_URL must be set")
    if not PAIR_TSV.exists():
        raise SystemExit(f"[STOP] missing: {PAIR_TSV}")

    eng = create_engine(db_url)

    pairs = pd.read_csv(PAIR_TSV, sep="\t", low_memory=False)
    need = {"roi_path", "cam", "channel", "wavelength_nm"}
    miss = sorted(list(need - set(pairs.columns)))
    if miss:
        raise SystemExit(f"[STOP] missing columns in {PAIR_TSV}: {miss}")

    pairs["roi_path"] = pairs["roi_path"].astype(str).str.strip()
    pairs["cam"] = pairs["cam"].astype(str).str.strip()
    pairs["channel"] = pairs["channel"].astype(str).str.strip()
    pairs["wavelength_nm"] = pd.to_numeric(pairs["wavelength_nm"], errors="coerce").astype("Int64")

    with eng.begin() as cx:
        rois = pd.read_sql(
            text(
                """
                SELECT id::uuid AS roi_id, roi_code, roi_path
                FROM public.imaging_roi_annotations
                WHERE coalesce(btrim(roi_path),'') <> '';
                """
            ),
            cx,
        )

    rois["roi_path"] = rois["roi_path"].astype(str).str.strip()

    m = pairs.merge(rois, on="roi_path", how="inner")
    if m.empty:
        raise SystemExit("[STOP] 0 matches between roi_channel_pairs_true.tsv and public.imaging_roi_annotations.roi_path")

    out = (
        m[["roi_id", "roi_code", "roi_path", "cam", "channel", "wavelength_nm"]]
        .dropna(subset=["roi_id"])
        .drop_duplicates()
        .copy()
    )
    out["keep"] = True
    out["kill_reason"] = None
    out["source"] = "v4_true_pairs"

    with eng.begin() as cx:
        cx.execute(text("DELETE FROM public.imaging_roi_channel_qc_v2 WHERE source = 'v4_true_pairs';"))
        cx.execute(
            text(
                """
                INSERT INTO public.imaging_roi_channel_qc_v2
                  (roi_id, roi_code, roi_path, cam, channel, wavelength_nm, keep, kill_reason, source)
                VALUES
                  (:roi_id, :roi_code, :roi_path, :cam, :channel, :wavelength_nm, :keep, :kill_reason, :source)
                ON CONFLICT (roi_id, cam, channel, wavelength_nm) DO UPDATE
                SET
                  keep = EXCLUDED.keep,
                  kill_reason = EXCLUDED.kill_reason,
                  source = EXCLUDED.source,
                  roi_code = EXCLUDED.roi_code,
                  roi_path = EXCLUDED.roi_path,
                  updated_at = now();
                """
            ),
            out.to_dict(orient="records"),
        )

    print("[OK] matched_rois:", int(out["roi_id"].nunique()))
    print("[OK] inserted_rows:", int(len(out)))

if __name__ == "__main__":
    main()
