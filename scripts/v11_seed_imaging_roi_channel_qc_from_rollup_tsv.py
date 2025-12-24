from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text


CLUSTER_PREFIX = "/clusterfs/vast/abcabc/"
SRC = "v4_rollup_cartesian"

ROLLUP = Path("seed_kits/legacy_wrangling_v4/working/2025-12-22-163559-roi_channels_by_roi_root.tsv")


def _real(v) -> bool:
    if v is None:
        return False
    s = str(v).strip()
    return s != "" and s.lower() not in ("nan", "none", "na", "n/a", "<na>")


def _split_semi(v) -> list[str]:
    if not _real(v):
        return []
    return [x.strip() for x in str(v).split(";") if x.strip()]


def main() -> None:
    db_url = os.environ.get("DB_URL")
    if not db_url:
        raise SystemExit("[STOP] DB_URL must be set")
    eng = create_engine(db_url)

    if not ROLLUP.exists():
        raise SystemExit(f"[STOP] missing rollup TSV: {ROLLUP}")

    df = pd.read_csv(ROLLUP, sep="\t", low_memory=False)
    df.columns = [str(c).strip() for c in df.columns]

    need = {"roi_root", "cams", "channels", "wavelengths_nm"}
    missing = sorted(list(need - set(df.columns)))
    if missing:
        raise SystemExit(f"[STOP] rollup TSV missing columns: {missing}")

    rows = []
    for r in df.itertuples(index=False):
        roi_root = str(getattr(r, "roi_root") or "").strip().lstrip("./")
        if not roi_root:
            continue

        roi_path = roi_root
        if not roi_path.startswith(CLUSTER_PREFIX):
            roi_path = CLUSTER_PREFIX + roi_path

        cams = _split_semi(getattr(r, "cams", None))
        chs = _split_semi(getattr(r, "channels", None))
        wvs = _split_semi(getattr(r, "wavelengths_nm", None))

        if not cams:
            cams = [pd.NA]
        if not chs:
            continue
        if not wvs:
            wvs = [pd.NA]

        for cam in cams:
            for ch in chs:
                for w in wvs:
                    w_i = None
                    if _real(w):
                        try:
                            w_i = int(str(w).strip())
                        except Exception:
                            w_i = None
                    rows.append((roi_path, cam, str(ch).strip(), w_i))

    if not rows:
        raise SystemExit("[STOP] no rows expanded from rollup TSV")

    df_exp = pd.DataFrame(rows, columns=["roi_path", "cam", "channel", "wavelength_nm"])
    df_exp = df_exp.drop_duplicates()

    with eng.begin() as cx:
        roi_map = pd.read_sql(
            text(
                """
                SELECT roi_code, roi_path
                FROM public.imaging_roi_annotations
                WHERE roi_path IS NOT NULL
                  AND btrim(roi_path) <> '';
                """
            ),
            cx,
        )

    m = df_exp.merge(roi_map, on="roi_path", how="inner")
    if m.empty:
        raise SystemExit("[STOP] 0 matches joining rollup rows to imaging_roi_annotations on roi_path")

    out = m[["roi_code", "cam", "channel", "wavelength_nm"]].drop_duplicates().copy()
    out["keep"] = True
    out["kill_reason"] = pd.NA
    out["source"] = SRC

    roi_codes = sorted(out["roi_code"].astype(str).unique().tolist())

    with eng.begin() as cx:
        cx.execute(
            text(
                """
                DELETE FROM public.imaging_roi_channel_qc
                WHERE source = :src
                  AND roi_code = ANY(CAST(:roi_codes AS text[]));
                """
            ),
            {"src": SRC, "roi_codes": roi_codes},
        )

        cx.execute(
            text(
                """
                INSERT INTO public.imaging_roi_channel_qc
                  (roi_code, cam, channel, wavelength_nm, keep, kill_reason, source)
                VALUES
                  (:roi_code, :cam, :channel, :wavelength_nm, :keep, :kill_reason, :source);
                """
            ),
            out.to_dict(orient="records"),
        )

    print("[OK] rollup_roi_paths:", int(df_exp["roi_path"].nunique()))
    print("[OK] matched_rois:", int(out["roi_code"].nunique()))
    print("[OK] inserted_rows:", int(len(out)))


if __name__ == "__main__":
    main()
