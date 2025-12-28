#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

V5_DIR = REPO_ROOT / "seed_kits" / "legacy_wrangling_v5" / "working" / "snapshots"
V5_CHANNELS_GLOB = "roi_channel_counts_v5_*.csv"
V5_BASEMAP_GLOB = "roi_path_to_session_markers_v5_manual_*.csv"


def run(cmd: list[str]) -> None:
    print("\n[RUN]", " ".join(cmd))
    subprocess.run(cmd, check=True)


def require_env(k: str) -> None:
    if not os.environ.get(k):
        raise SystemExit(f"[STOP] missing env var: {k}")


def newest_snapshot_csv(glob_pat: str) -> Path:
    if not V5_DIR.exists():
        raise SystemExit(f"[STOP] missing snapshots dir: {V5_DIR}")
    cands = sorted(V5_DIR.glob(glob_pat))
    if not cands:
        raise SystemExit(f"[STOP] no snapshots found: {V5_DIR}/{glob_pat}")
    return cands[-1]


def assert_transgene_alleles_exist() -> None:
    code = (
        "import os\n"
        "from sqlalchemy import create_engine, text\n"
        "url=os.environ.get('DB_URL')\n"
        "eng=create_engine(url)\n"
        "with eng.begin() as cx:\n"
        "  n = cx.execute(text('select count(*) from public.transgene_alleles')).scalar()\n"
        "n = int(n or 0)\n"
        "print('TRANS_GENE_ALLELES_ROWS', n)\n"
        "if n == 0:\n"
        "  raise SystemExit('[STOP] public.transgene_alleles is empty; run foundation pipeline first')\n"
    )
    run(["python", "-c", code])


def psql_stdin(sql: str) -> None:
    db_url = os.environ["DB_URL"]
    print("\n[RUN] psql (stdin)")
    subprocess.run(
        ["psql", db_url, "-X", "-v", "ON_ERROR_STOP=1"],
        input=sql.encode("utf-8"),
        check=True,
    )


def load_legacy_v5_roi_channels() -> None:
    src = newest_snapshot_csv(V5_CHANNELS_GLOB)
    print(f"[V5] roi_channels snapshot: {src}")

    run(["psql", os.environ["DB_URL"], "-X", "-v", "ON_ERROR_STOP=1", "-c", "TRUNCATE TABLE public.legacy_roi_channels_v5;"])

    sql = (
        f"\\copy public.legacy_roi_channels_v5 (roi_path, channel_name, n_tiffs) FROM '{src.as_posix()}' WITH (FORMAT csv, HEADER true);\n"
        "SELECT\n"
        "  count(*) AS rows_loaded,\n"
        "  count(distinct roi_path) AS roi_paths,\n"
        "  count(distinct channel_name) AS channel_names,\n"
        "  sum(n_tiffs) AS sum_n_tiffs\n"
        "FROM public.legacy_roi_channels_v5;\n"
    )
    psql_stdin(sql)


def load_legacy_v5_roi_path_map() -> None:
    src = newest_snapshot_csv(V5_BASEMAP_GLOB)
    print(f"[V5] roi_path_map snapshot: {src}")

    run(["psql", os.environ["DB_URL"], "-X", "-v", "ON_ERROR_STOP=1", "-c", "TRUNCATE TABLE public.legacy_roi_path_map_v5;"])

    sql = (
        f"\\copy public.legacy_roi_path_map_v5 (roi_path, date_mount_id, genotype_base_codes, genotype_allele_codes, treatment_rna_base_codes, treatment_plasmid_base_codes) FROM '{src.as_posix()}' WITH (FORMAT csv, HEADER true);\n"
        "SELECT\n"
        "  count(*) AS rows_loaded,\n"
        "  count(distinct roi_path) AS roi_paths\n"
        "FROM public.legacy_roi_path_map_v5;\n"
    )
    psql_stdin(sql)


def main() -> None:
    require_env("DB_URL")
    print("[DB_URL]", os.environ["DB_URL"])

    run(["python", "scripts/foundation_run_pipeline.py"])
    assert_transgene_alleles_exist()

    load_legacy_v5_roi_channels()
    load_legacy_v5_roi_path_map()

    print("\n[OK] legacy v5 full local load pipeline completed cleanly")


if __name__ == "__main__":
    main()
