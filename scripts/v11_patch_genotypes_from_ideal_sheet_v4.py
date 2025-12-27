from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text


def _s(x: object) -> str:
    if x is None:
        return ""
    s = str(x).strip()
    if s.lower() in ("nan", "none", "na", "n/a", "<na>"):
        return ""
    return s


def _canon_codes_pipe(blob: object) -> str:
    s = _s(blob).lower()
    if not s:
        return ""
    toks = [t.strip() for t in re.split(r"[|,;]+", s) if t.strip()]
    out: list[str] = []
    seen: set[str] = set()
    for t in toks:
        t = re.sub(r"[^a-z0-9\-]+", "", t)
        m = re.match(r"^([a-z]+)-?0*([0-9]+)$", t)
        if m:
            t = f"{m.group(1)}-{int(m.group(2))}"
        if t and t not in seen:
            seen.add(t)
            out.append(t)
    return "|".join(out)


def _norm_alleles_pipe(blob: object) -> str:
    s = _s(blob)
    if not s:
        return ""
    parts = [p.strip() for p in s.replace(",", "|").replace(";", "|").split("|") if p.strip()]
    out: list[str] = []
    for p in parts:
        try:
            f = float(p)
            out.append(str(int(f)) if f.is_integer() else str(p).strip())
        except Exception:
            out.append(str(p).strip())
    seen: set[str] = set()
    uniq: list[str] = []
    for x in out:
        if x and x not in seen:
            seen.add(x)
            uniq.append(x)
    return "|".join(uniq)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in-tsv", default="seed_kits/legacy_wrangling_v4/working/ideal_imaging_import_sheet_v4.fixed.tsv")
    ap.add_argument("--out-csv", required=True)
    ap.add_argument("--db-url", default=None)
    ap.add_argument("--only-slug", default="", help="optional substring filter on dataset_slug (e.g. mem-histone, mem-mito)")
    args = ap.parse_args()

    db_url = args.db_url or _s(__import__("os").environ.get("DB_URL"))
    if not db_url:
        raise SystemExit("[STOP] DB_URL is not set (export it or pass --db-url)")

    inp = Path(args.in_tsv)
    out = Path(args.out_csv)
    if not inp.exists():
        raise SystemExit(f"[STOP] missing input TSV: {inp}")

    df = pd.read_csv(inp, sep="\t", dtype=str, keep_default_na=False, na_filter=False)
    df.columns = [str(c).strip() for c in df.columns]

    need_cols = ["roi_path", "dataset_slug", "include_in_db", "genotype_base_codes", "genotype_allele_codes"]
    miss = [c for c in need_cols if c not in df.columns]
    if miss:
        raise SystemExit(f"[STOP] input TSV missing columns: {miss}")

    df["roi_path"] = df["roi_path"].map(_s)
    df = df[df["roi_path"].ne("")].copy()

    df["include_in_db"] = df["include_in_db"].astype(str).str.strip().str.lower().isin(["1", "t", "true", "y", "yes"])
    df = df[df["include_in_db"]].copy()

    if args.only_slug.strip():
        needle = args.only_slug.strip().lower()
        df = df[df["dataset_slug"].astype(str).str.lower().str.contains(needle, na=False)].copy()

    df["genotype_base_codes"] = df["genotype_base_codes"].map(_canon_codes_pipe)
    df["genotype_allele_codes"] = df["genotype_allele_codes"].map(_norm_alleles_pipe)

    blank = (df["genotype_base_codes"].eq("") | df["genotype_allele_codes"].eq(""))
    n_blank = int(blank.sum())
    if n_blank:
        df = df[~blank].copy()

    if df.empty:
        out.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(
            columns=[
                "clutch_code",
                "legacy_clutch_key",
                "genotype_basecodes",
                "genotype_allele_nicknames",
                "genotype_alleles_display",
                "date_born",
                "roi_count",
            ]
        ).to_csv(out, index=False)
        print(str(out))
        print("ROWS 0")
        print(f"[INFO] skipped {n_blank} ROI row(s) with blank genotype fields in ideal sheet")
        return

    eng = create_engine(db_url)

    roi_paths = df["roi_path"].tolist()
    with eng.begin() as cx:
        rows = cx.execute(
            text(
                """
                SELECT
                  ira.roi_path,
                  c.clutch_code,
                  c.legacy_clutch_key
                FROM public.imaging_roi_annotations ira
                JOIN public.imaging_clutch_memberships m ON m.slot_id = ira.slot_id
                JOIN public.clutches c ON c.id = m.clutch_id
                WHERE ira.roi_path = ANY(:paths)
                """
            ),
            {"paths": roi_paths},
        ).fetchall()

    map_df = pd.DataFrame(rows, columns=["roi_path", "clutch_code", "legacy_clutch_key"])
    map_df = map_df[["roi_path", "clutch_code", "legacy_clutch_key"]].drop_duplicates().copy()
    map_df["roi_path"] = map_df["roi_path"].map(_s)
    map_df["clutch_code"] = map_df["clutch_code"].map(_s)
    map_df["legacy_clutch_key"] = map_df["legacy_clutch_key"].map(_s)

    for _c in ["clutch_code","legacy_clutch_key","clutch_code_x","clutch_code_y","legacy_clutch_key_x","legacy_clutch_key_y"]:
        if _c in df.columns:
            df = df.drop(columns=[_c])
    df = df.merge(map_df, on="roi_path", how="left", validate="m:1")

    unmapped = df["clutch_code"].map(_s).eq("")
    if int(unmapped.sum()):
        sample = df.loc[unmapped, ["roi_path"]].head(30).to_string(index=False)
        raise SystemExit("[STOP] some roi_path did not map to a clutch_code in DB.\n" + sample)

    bad_key = df["legacy_clutch_key"].map(_s).eq("")
    if int(bad_key.sum()):
        sample = df.loc[bad_key, ["clutch_code", "roi_path"]].drop_duplicates().head(50).to_string(index=False)
        raise SystemExit("[STOP] some mapped clutches have empty legacy_clutch_key in DB (loader requires it).\n" + sample)

    def uniq1(series: pd.Series) -> str:
        vals = [v for v in series.astype(str).map(_s).tolist() if v]
        vals = sorted(set(vals))
        if len(vals) != 1:
            raise ValueError("; ".join(vals[:10]) if vals else "")
        return vals[0]

    per = (
        df.groupby(["clutch_code", "legacy_clutch_key"], as_index=False)
        .agg(
            genotype_basecodes=("genotype_base_codes", uniq1),
            genotype_allele_nicknames=("genotype_allele_codes", uniq1),
        )
        .copy()
    )

    per["genotype_alleles_display"] = per["genotype_basecodes"].astype(str) + " " + per["genotype_allele_nicknames"].astype(str)
    per["date_born"] = ""
    per["roi_count"] = "0"

    out.parent.mkdir(parents=True, exist_ok=True)
    per[
        [
            "clutch_code",
            "legacy_clutch_key",
            "genotype_basecodes",
            "genotype_allele_nicknames",
            "genotype_alleles_display",
            "date_born",
            "roi_count",
        ]
    ].to_csv(out, index=False)

    print(str(out))
    print("ROWS", len(per))
    if n_blank:
        print(f"[INFO] skipped {n_blank} ROI row(s) with blank genotype fields in ideal sheet")


if __name__ == "__main__":
    main()
