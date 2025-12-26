from __future__ import annotations

import argparse
import os
import re
from datetime import date
from typing import Optional, List, Dict

import pandas as pd
from sqlalchemy import text, create_engine
from sqlalchemy.engine import Engine
from pathlib import Path


def get_engine(db_url: Optional[str] = None) -> Engine:
    url = db_url or os.environ.get("DB_URL")
    if not url:
        raise SystemExit("[STOP] DB_URL is not set")
    print(f"DB_URL={url}")
    return create_engine(url)


EXPERIMENT_FOLDER_RE = re.compile(r"/(20\d{6}_[^/]+)/")


def experiment_name_from_roi_path(roi_path: object) -> Optional[str]:
    if roi_path is None:
        return None
    s = str(roi_path)
    if not s or s.lower() in ("nan", "none"):
        return None
    m = EXPERIMENT_FOLDER_RE.search(s)
    if not m:
        return None
    return m.group(1)


def experiment_date_from_plate_date(plate_date: object) -> Optional[date]:
    if plate_date is None or (isinstance(plate_date, float) and pd.isna(plate_date)):
        return None
    try:
        d_int = int(float(plate_date))
    except Exception:
        return None
    s = str(d_int)
    if len(s) != 8:
        return None
    try:
        return date(int(s[0:4]), int(s[4:6]), int(s[6:8]))
    except Exception:
        return None


def plate_code_from_row(row: pd.Series) -> str:
    plate_date = row.get("plate_date")
    plate_id = row.get("plate_id_filled")
    if pd.isna(plate_date) or pd.isna(plate_id):
        raise ValueError(f"Missing plate_date/plate_id_filled for bruker_roi_id={row.get('bruker_roi_id')}")
    d_int = int(float(plate_date))
    plate_num = int(float(plate_id))
    return f"{d_int}-plate{plate_num}"


def upsert_imaging_plates(df: pd.DataFrame, engine: Engine) -> None:
    df = df.copy()
    if "roi_note_anatomy" in df.columns:
        df["roi_note_anatomy"] = df["roi_note_anatomy"].astype(str).map(lambda x: "" if x.strip().lower() in ("nan","none","<na>") else x.strip())
    else:
        df["roi_note_anatomy"] = ""
    if "n_tiffs" in df.columns:
        df["n_tiffs"] = pd.to_numeric(df["n_tiffs"], errors="coerce").fillna(0).astype(int)
    else:
        df["n_tiffs"] = 0

    df["plate_code"] = df.apply(plate_code_from_row, axis=1)
    df["experiment_date"] = df["plate_date"].apply(experiment_date_from_plate_date)

    experiment_name_col = "dataset_slug" if "dataset_slug" in df.columns else None
    df["experiment_name_inferred"] = df["roi_dir"].apply(experiment_name_from_roi_path) if "roi_dir" in df.columns else None

    cols = ["plate_code", "experiment_date"]
    if experiment_name_col:
        cols.append(experiment_name_col)
    cols.append("experiment_name_inferred")

    plates = df[cols].drop_duplicates(subset=["plate_code"]).copy()

    def pick_exp(row: pd.Series) -> Optional[str]:
        if experiment_name_col:
            v = row.get(experiment_name_col)
            if isinstance(v, str) and v.strip():
                return v.strip()
        v2 = row.get("experiment_name_inferred")
        if isinstance(v2, str) and v2.strip():
            return v2.strip()
        return None

    plates["experiment_name"] = plates.apply(pick_exp, axis=1)

    sql = text(
        """
        INSERT INTO public.imaging_plates (
            plate_code,
            experiment_date,
            experiment_name
        )
        VALUES (
            :plate_code,
            :experiment_date,
            :experiment_name
        )
        ON CONFLICT (plate_code) DO UPDATE
        SET
            experiment_date = EXCLUDED.experiment_date,
            experiment_name = EXCLUDED.experiment_name
        """
    )

    with engine.begin() as conn:
        for _, row in plates.iterrows():
            conn.execute(
                sql,
                {
                    "plate_code": row["plate_code"],
                    "experiment_date": row["experiment_date"],
                    "experiment_name": row.get("experiment_name"),
                },
            )


def _norm_orient(x: object) -> str:
    s = "" if x is None else str(x)
    s = s.replace("\u00a0", " ").strip()
    if s.lower() in ("nan", "none", "<na>"):
        return ""
    return s


def upsert_imaging_slots(df: pd.DataFrame, engine: Engine) -> None:
    if "slot_id_filled" not in df.columns:
        raise SystemExit("Required column 'slot_id_filled' not found in CSV")

    df = df.copy()
    df["plate_code"] = df.apply(plate_code_from_row, axis=1)
    df["slot_index"] = df["slot_id_filled"].astype(int)
    df["slot_label"] = df["slot_index"].apply(lambda i: f"slot{i}")

    orient_col = None
    if "Mounting Orientation" in df.columns:
        orient_col = "Mounting Orientation"
    elif "orientation" in df.columns:
        orient_col = "orientation"

    if orient_col is not None:
        df["_orientation"] = df[orient_col].map(_norm_orient)
        by = (
            df.groupby(["plate_code", "slot_index"])["_orientation"]
            .apply(lambda s: sorted({x for x in s.astype(str) if x.strip()}))
            .reset_index(name="_vals")
        )
        bad = by[by["_vals"].map(len).gt(1)].copy()
        if len(bad):
            raise SystemExit(
                "[STOP] conflicting orientation values within the same (plate_code, slot_index). Examples:\n"
                + bad.head(50).to_string(index=False)
            )
        df_or = by.copy()
        df_or["orientation"] = df_or["_vals"].map(lambda xs: xs[0] if xs else "")
        df_or = df_or.drop(columns=["_vals"])
    else:
        df_or = df[["plate_code", "slot_index"]].drop_duplicates().copy()
        df_or["orientation"] = ""

    slots = df[["plate_code", "slot_index", "slot_label"]].drop_duplicates(subset=["plate_code", "slot_index"])
    slots = slots.merge(df_or, on=["plate_code", "slot_index"], how="left")

    sql = text(
        """
        WITH plate AS (
          SELECT id AS plate_id
          FROM public.imaging_plates
          WHERE plate_code = :plate_code
        )
        INSERT INTO public.imaging_slots (
            plate_id,
            slot_index,
            slot_label,
            well_row,
            well_col,
            slot_note,
            orientation
        )
        SELECT
            plate_id,
            :slot_index,
            :slot_label,
            NULL,
            NULL,
            NULL,
            NULLIF(:orientation, '')
        FROM plate
        ON CONFLICT (plate_id, slot_index) DO UPDATE
        SET
            slot_label  = EXCLUDED.slot_label,
            orientation = COALESCE(EXCLUDED.orientation, public.imaging_slots.orientation)
        """
    )

    with engine.begin() as conn:
        for _, row in slots.iterrows():
            conn.execute(
                sql,
                {
                    "plate_code": row["plate_code"],
                    "slot_index": int(row["slot_index"]),
                    "slot_label": row["slot_label"],
                    "orientation": _norm_orient(row.get("orientation")),
                },
            )


ROI_OBSERVATIONS_TSV_DEFAULT = "seed_kits/legacy_wrangling_v4/working/roi_observations.tsv"
_RE_TRAIL_SLASH = re.compile(r"/+$")
_RE_ROI_SLASH = re.compile(r"/roi(?P<idx>\d+)(?:_(?P<label>[A-Za-z0-9][A-Za-z0-9_-]*))?$", re.IGNORECASE)
_RE_ROI_UNDERSCORE = re.compile(r"_roi(?P<idx>\d+)(?:_(?P<label>[A-Za-z0-9][A-Za-z0-9_-]*))?$", re.IGNORECASE)


def _guess_n_tiffs_from_obs(file_exts: object, n_paths: object) -> int:
    ex = "" if file_exts is None else str(file_exts).lower()
    try:
        n = int(float(n_paths)) if n_paths is not None and str(n_paths).strip() != "" else 0
    except Exception:
        n = 0
    if "tif" in ex:
        return max(n, 0)
    return 0

def _infer_anatomy_from_roi_dir(roi_dir: object) -> str:
    if roi_dir is None:
        return ""
    s = str(roi_dir).replace("\u00a0", " ").strip()
    if not s or s.lower() in ("nan", "none", "<na>"):
        return ""
    s = _RE_TRAIL_SLASH.sub("", s)

    m = _RE_ROI_SLASH.search(s)
    if not m:
        m = _RE_ROI_UNDERSCORE.search(s)

    if not m:
        return ""

    lab = (m.group("label") or "").strip()
    if not lab:
        return ""

    if lab.isdigit():
        return ""

    return lab


def _norm_code_element(x: object) -> str:
    s = "" if x is None else str(x).strip().lower()
    if not s or s in ("nan","none","na","n/a","<na>"):
        return ""
    s = re.sub(r"[^a-z0-9_]+", "_", s)   # keep '_' within element
    s = re.sub(r"_+", "_", s).strip("_")
    return s

def _norm_elem(s: str) -> str:
    s = "" if s is None else str(s)
    s = s.strip().lower()
    # within-element delimiter: underscore
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s

def _roi_code_from_path(roi_path: object) -> str:
    """
    Global rule:
      - '-' between elements
      - '_' within elements
    We derive roi_code from the ROI's full path so roi_path -> roi_code is injective
    (modulo normalization; collisions get a short -h<md5> suffix).
    """
    if roi_path is None:
        return ""
    s = str(roi_path).strip()
    if not s or s.lower() in ("nan","none","na","n/a","<na>"):
        return ""

    # Normalize slashes
    s = re.sub(r"/+", "/", s)

    # Identify dataset + experiment folder + roi_rel (path under experiment folder)
    # Expected: .../(Aang_Foundation|Korra_Foundation)/<experiment_folder>/<roi_rel...>
    m = re.search(r"/(Aang_Foundation|Korra_Foundation)/([^/]+)/(.+)$", s)
    if m:
        foundation_long = m.group(1)
        exp_folder = m.group(2)
        roi_rel = m.group(3)
        dataset = "aang" if "Aang_Foundation" in foundation_long else "korra"
    else:
        # Fallback: if it doesn't match, still make something stable from basename-ish
        dataset = ""
        exp_folder = ""
        roi_rel = s.lstrip("/")

    # Split roi_rel into segments, normalize each segment, then join with '-'
    rel_segs = [seg for seg in roi_rel.split("/") if seg]
    rel_norm = "-".join(_norm_elem(seg) for seg in rel_segs if _norm_elem(seg))

    parts = [dataset, _norm_elem(exp_folder), rel_norm]
    parts = [p for p in parts if p]
    return "-".join(parts)

ROI_N_TIFFS_TSV_DEFAULT = "seed_kits/legacy_wrangling_v4/working/roi_n_tiffs_by_roi_path.tsv"

def insert_imaging_rois(df: pd.DataFrame, engine: Engine) -> None:
    required_cols = [
        "plate_date",
        "plate_id_filled",
        "slot_id_filled",
        "roi_index_within_slot",
        "roi_dir",
        "bruker_roi_id",
    ]
    for col in required_cols:
        if col not in df.columns:
            raise SystemExit(f"Required column '{col}' not found in CSV")

    df = df.copy()
    df["plate_code"] = df.apply(plate_code_from_row, axis=1)
    df["slot_index"] = df["slot_id_filled"].astype(int)
    df["roi_index_int"] = df["roi_index_within_slot"].astype(int)
    # Canonical identity is roi_path; roi_code is a globally-unique display code derived from path.
    df["roi_path"] = df["roi_dir"].astype(str).str.strip()
    if "roi_note_anatomy" not in df.columns:
        df["roi_note_anatomy"] = ""

    # Attach n_tiffs from precomputed TSV (roi_path -> n_tiffs)
    df["roi_path_key"] = df["roi_path"].astype(str).str.strip()
    df["roi_path_key"] = df["roi_path_key"].str.replace(r"/+", "/", regex=True).str.rstrip("/")

    n_tiffs_path = Path(ROI_N_TIFFS_TSV_DEFAULT)
    if n_tiffs_path.exists():
        df_nt = pd.read_csv(n_tiffs_path, sep="\t", low_memory=False, dtype=str, keep_default_na=False, na_filter=False)
        df_nt.columns = [str(c).strip() for c in df_nt.columns]
        if "roi_path" not in df_nt.columns or "n_tiffs" not in df_nt.columns:
            raise SystemExit(f"[STOP] n_tiffs TSV missing roi_path/n_tiffs columns: {n_tiffs_path}")

        df_nt = df_nt.copy()
        df_nt["roi_path_key"] = df_nt["roi_path"].astype(str).str.strip()
        df_nt["roi_path_key"] = df_nt["roi_path_key"].str.replace(r"/+", "/", regex=True).str.rstrip("/")
        df_nt["n_tiffs"] = pd.to_numeric(df_nt["n_tiffs"], errors="coerce").fillna(0).astype(int)

        any_positive = int((df_nt["n_tiffs"] > 0).sum())
        df = df.merge(df_nt[["roi_path_key", "n_tiffs"]], on="roi_path_key", how="left")

        df["n_tiffs"] = pd.to_numeric(df["n_tiffs"], errors="coerce").fillna(0).astype(int)
        join_hits = int((df["n_tiffs"] > 0).sum())
        print(f"[N_TIFFS] tsv={n_tiffs_path} rows={len(df_nt)} any_positive={any_positive} join_hits_gt0={join_hits}")

        if any_positive > 0 and join_hits == 0:
            ex = df[["roi_path"]].head(25)
            raise SystemExit("[STOP] n_tiffs TSV exists and has positive counts, but join_hits_gt0=0. Example roi_path values:\n" + ex.to_string(index=False))
    else:
        df["n_tiffs"] = 0

    if "n_tiffs" not in df.columns:
        df["n_tiffs"] = 0
    df["n_tiffs"] = pd.to_numeric(df["n_tiffs"], errors="coerce").fillna(0).astype(int)

    df["roi_code"] = df["roi_path"].map(_roi_code_from_path)

    # If normalization still collides, make it globally unique by adding a short hash suffix.
    # (Never uses "__"; uses "-h<8hex>" and only when needed.)
    _base = df["roi_code"].astype(str).fillna("").str.strip()
    _n = _base.groupby(_base).transform("size")
    need_hash = (_n > 1) & (_base != "")
    if int(need_hash.sum()) != 0:
        import hashlib
        def _h(x: str) -> str:
            return hashlib.md5(x.encode("utf-8")).hexdigest()[:8]
        df.loc[need_hash, "roi_code"] = (
            df.loc[need_hash, "roi_code"].astype(str).str.strip()
            + "-h"
            + df.loc[need_hash, "roi_path"].astype(str).map(_h)
        )

    bad_code = df["roi_code"].isna() | df["roi_code"].astype(str).str.strip().eq("")
    if int(bad_code.sum()) != 0:
        ex = df.loc[bad_code, ["plate_code", "slot_index", "roi_index_int", "roi_dir"]].head(50)
        raise SystemExit(f"[STOP] {int(bad_code.sum())} ROI row(s) produced blank roi_code (check roi_path parsing). Examples:\n{ex.to_string(index=False)}")


    plate_codes = sorted(set(df["plate_code"].astype(str).str.strip().tolist()))
    if not plate_codes:
        raise SystemExit("[STOP] no plate_code values computed from input CSV")

    delete_in_feed_sql = text(
        """
        DELETE FROM public.imaging_roi_annotations ira
        USING public.imaging_slots s, public.imaging_plates p
        WHERE ira.slot_id = s.id
          AND s.plate_id = p.id
          AND p.plate_code = ANY(CAST(:plate_codes AS text[]));
        """
    )

    delete_stale_legacy_sql = text(
        """
        DELETE FROM public.imaging_roi_annotations ira
        USING public.imaging_slots s, public.imaging_plates p
        WHERE ira.slot_id = s.id
          AND s.plate_id = p.id
          AND p.plate_code <> ALL(CAST(:plate_codes AS text[]))
          AND (
            ira.roi_path ILIKE '%/Aang_Foundation/%'
            OR ira.roi_path ILIKE '%/Korra_Foundation/%'
          );
        """
    )

    sql = text(
        """
        WITH plate AS (
          SELECT id AS plate_id
          FROM public.imaging_plates
          WHERE plate_code = :plate_code
        ),
        slot AS (
          SELECT s.id AS slot_id
          FROM public.imaging_slots s
          JOIN plate p ON p.plate_id = s.plate_id
          WHERE s.slot_index = :slot_index
        )
        INSERT INTO public.imaging_roi_annotations (
            slot_id,
            roi_index_within_slot,
            roi_code,
            roi_path,
            roi_note_anatomy,
            n_tiffs
        )
        SELECT
            slot_id,
            :roi_index_within_slot,
            :roi_code,
            :roi_path,
            NULLIF(CAST(:roi_note_anatomy AS text), ''),
            :n_tiffs
        FROM slot
        ON CONFLICT (slot_id, roi_index_within_slot) DO UPDATE
        SET roi_code         = EXCLUDED.roi_code,
            roi_path         = EXCLUDED.roi_path,
            roi_note_anatomy = EXCLUDED.roi_note_anatomy,
            n_tiffs          = EXCLUDED.n_tiffs
        """
    )

    with engine.begin() as conn:
        r1 = conn.execute(delete_in_feed_sql, {"plate_codes": plate_codes})
        r2 = conn.execute(delete_stale_legacy_sql, {"plate_codes": plate_codes})
        print(f"imaging_roi_annotations: deleted_in_feed={int(r1.rowcount or 0)} deleted_stale_legacy={int(r2.rowcount or 0)} plates_in_feed={len(plate_codes)}")

        upserted = 0
        for _, row in df.iterrows():
            _rna = row.get("roi_note_anatomy", "")
            if pd.isna(_rna):
                _rna = ""
            else:
                _rna = str(_rna).strip()
                if _rna.lower() in ("nan", "none", "<na>"):
                    _rna = ""

            params = {
                "plate_code": row["plate_code"],
                "slot_index": int(row["slot_index"]),
                "roi_index_within_slot": int(row["roi_index_int"]),
                "roi_code": row["roi_code"],
                "roi_path": row["roi_path"],
                "roi_note_anatomy": _rna,
                "n_tiffs": int(row.get("n_tiffs", 0) or 0),
            }
            conn.execute(sql, params)
            upserted += 1

        print(f"imaging_roi_annotations: inserted/updated={upserted}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Load legacy imaging ROIs into lean imaging tables (imaging_plates, imaging_slots, imaging_roi_annotations)."
    )
    parser.add_argument("--csv", required=True, help="Path to legacy_imaging_annotations_for_db_v9.csv (or compat)")
    parser.add_argument("--db-url", help="Postgres DB URL (overrides DB_URL env var)")
    args = parser.parse_args()

    engine = get_engine(args.db_url)
    df = pd.read_csv(args.csv, low_memory=False, dtype=str, keep_default_na=False, na_filter=False)
    df = df.fillna("")
    df.columns = [str(c).strip() for c in df.columns]

    needed = ["plate_date", "plate_id_filled", "slot_id_filled", "roi_index_within_slot", "roi_dir", "bruker_roi_id"]
    missing = [c for c in needed if c not in df.columns]
    if missing:
        raise SystemExit(f"[STOP] input CSV missing required columns: {missing}")

    upsert_imaging_plates(df, engine)
    upsert_imaging_slots(df, engine)
    insert_imaging_rois(df, engine)

    with engine.begin() as cx:
        n_plates = cx.execute(text("SELECT count(*) FROM public.imaging_plates")).scalar()
        n_slots  = cx.execute(text("SELECT count(*) FROM public.imaging_slots")).scalar()
        n_rois   = cx.execute(text("SELECT count(*) FROM public.imaging_roi_annotations")).scalar()

    print(f"[OK] v9_load_imaging_legacy_rois: plates={int(n_plates)}, slots={int(n_slots)}, rois={int(n_rois)}")


if __name__ == "__main__":
    main()
