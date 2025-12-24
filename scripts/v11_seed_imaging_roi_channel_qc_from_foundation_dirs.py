from __future__ import annotations

import os
import re
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

CLUSTER_PREFIX = "/clusterfs/vast/abcabc/"
SRC = "v4_scan"

CAM_RE = re.compile(r"\b(CamA|CamB)\b", re.IGNORECASE)
CH_RE = re.compile(r"_ch(\d+)\b", re.IGNORECASE)
NM_RE = re.compile(r"_(\d{3})nm\b", re.IGNORECASE)

def main() -> None:
    db_url = os.environ.get("DB_URL")
    if not db_url:
        raise SystemExit("[STOP] DB_URL must be set")
    eng = create_engine(db_url)

    p_list = Path("seed_kits/legacy_wrangling_v4/raw/2025-12-22-161855-foundation_dirs_depth6.txt")
    if not p_list.exists():
        raise SystemExit(f"[STOP] missing: {p_list}")

    rows: list[tuple[str, str, int | None]] = []
    with p_list.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            s = line.strip().lstrip("./")
            if not s:
                continue

            parts = s.split("/")
            if len(parts) < 4:
                continue
            foundation = parts[0]
            if foundation not in ("Aang_Foundation", "Korra_Foundation"):
                continue
            exp = parts[1]
            roi_folder = parts[2]
            roi_root_full = CLUSTER_PREFIX + f"{foundation}/{exp}/{roi_folder}"

            cam_m = CAM_RE.search(s)
            ch_m = CH_RE.search(s)
            nm_m = NM_RE.search(s)
            if not (cam_m and ch_m and nm_m):
                continue

            cam = cam_m.group(1)
            ch = int(ch_m.group(1))
            nm = int(nm_m.group(1))

            rows.append((roi_root_full, cam, ch, nm))

    if not rows:
        raise SystemExit("[STOP] no (cam, ch, nm) hits found in foundation_dirs_depth6.txt")

    df = pd.DataFrame(rows, columns=["roi_path", "cam", "ch_num", "wavelength_nm"])
    df = df.drop_duplicates()

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

    m = df.merge(roi_map, on="roi_path", how="inner")
    if m.empty:
        raise SystemExit("[STOP] 0 matches joining channel hits to imaging_roi_annotations on roi_path")

    out = (
        m[["roi_code", "cam", "ch_num", "wavelength_nm"]]
        .drop_duplicates()
        .rename(columns={"ch_num": "channel"})
        .copy()
    )
    out["channel"] = out["channel"].map(lambda n: f"ch{int(n)}")
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

        ins = text(
            """
            INSERT INTO public.imaging_roi_channel_qc
              (roi_code, cam, channel, wavelength_nm, keep, kill_reason, source)
            VALUES
              (:roi_code, :cam, :channel, :wavelength_nm, :keep, :kill_reason, :source);
            """
        )
        cx.execute(ins, out.to_dict(orient="records"))

    print("[OK] roi_paths_with_channels:", int(df["roi_path"].nunique()))
    print("[OK] matched_rois:", int(out["roi_code"].nunique()))
    print("[OK] inserted_rows:", int(len(out)))

if __name__ == "__main__":
    main()
