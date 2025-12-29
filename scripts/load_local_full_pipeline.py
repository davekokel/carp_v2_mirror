#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

SEED_KIT = REPO_ROOT / "seed_kits" / "2025-11-15-121231-autoload"

V5_SNAPSHOTS_DIR = REPO_ROOT / "seed_kits" / "legacy_wrangling_v5" / "working" / "snapshots"
V5_ROI_CHANNELS_GLOB = "roi_channel_counts_v5_*.csv"
V5_ROI_PATH_MAP_MANUAL_GLOB = "roi_path_to_session_markers_v5_manual_*.csv"
V5_NORMALIZE_SCRIPT = REPO_ROOT / "seed_kits" / "legacy_wrangling_v5" / "scripts" / "v5_normalize_roi_path_map_for_upload.py"

V5_WIDE_NORM = V5_SNAPSHOTS_DIR / "roi_path_to_session_markers_v5_normalized.csv"
V5_GENO_NORM = V5_SNAPSHOTS_DIR / "roi_genotype_constructs_v5_normalized.csv"
V5_TRT_NORM = V5_SNAPSHOTS_DIR / "roi_treatment_constructs_v5_normalized.csv"


def run(cmd: list[str]) -> None:
    print("\n[RUN]", " ".join(str(x) for x in cmd))
    subprocess.run([str(x) for x in cmd], check=True)


def require_env(k: str) -> None:
    if not os.environ.get(k):
        raise SystemExit(f"[STOP] missing env var: {k}")


def psql_stdin(db_url: str, sql: str) -> None:
    print("\n[RUN] psql (stdin)")
    subprocess.run(
        ["psql", db_url, "-X", "-v", "ON_ERROR_STOP=1"],
        input=sql.encode("utf-8"),
        check=True,
    )


def psql_one(db_url: str, sql: str) -> None:
    run(["psql", db_url, "-X", "-v", "ON_ERROR_STOP=1", "-c", sql])


def newest_snapshot(glob_pat: str) -> Path:
    if not V5_SNAPSHOTS_DIR.exists():
        raise SystemExit(f"[STOP] missing snapshots dir: {V5_SNAPSHOTS_DIR}")
    cands = sorted(V5_SNAPSHOTS_DIR.glob(glob_pat))
    if not cands:
        raise SystemExit(f"[STOP] no snapshots found: {V5_SNAPSHOTS_DIR}/{glob_pat}")
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


def load_modern_seed_data() -> None:
    run(["python", "scripts/v8_load_fluors_tags_fusions.py", "--fluors-csv", str(SEED_KIT / "fluors.csv"), "--tags-file", str(SEED_KIT / "tags.xlsx")])
    run(["python", "scripts/v8_load_fluor_aliases_from_csv.py", "--alias-csv", str(SEED_KIT / "alias.csv")])
    run(["python", "-m", "carp_app.etl.loader_dyes", "--csv", str(SEED_KIT / "dyes.csv")])
    run(["python", "scripts/v10_load_constructs_from_csv.py", "--constructs-csv", str(SEED_KIT / "constructs_plasmid.csv")])
    run(["python", "scripts/v10_load_construct_fusions_from_csv.py", "--constructs-csv", str(SEED_KIT / "constructs_plasmid.csv")])
    run(["python", "scripts/v9_build_genetic_backgrounds_seed.py"])
    run(["python", "scripts/v9_load_genetic_backgrounds_seed.py"])
    run(["python", "scripts/v11_seed_fish_transgenics_from_csv.py", "--csv", str(SEED_KIT / "fish_transgenics.csv")])
    run(["python", "scripts/v11_seed_fish_treated_from_csv.py", "--csv", str(SEED_KIT / "fish_treated.csv")])
    run(["python", "scripts/v11_seed_fish_transgene_alleles_from_lines.py"])


def ensure_tanks_for_all_fish(db_url: str) -> None:
    sql = (
        "INSERT INTO public.tanks (tank_code, fish_instance_id, status, notes)\n"
        "SELECT f.fish_code || '-TANK1' AS tank_code, f.id AS fish_instance_id, 'active' AS status, NULL AS notes\n"
        "FROM public.fish_instances_v10 f\n"
        "WHERE f.fish_code IS NOT NULL\n"
        "  AND NOT EXISTS (\n"
        "    SELECT 1\n"
        "    FROM public.tanks t\n"
        "    WHERE t.fish_instance_id = f.id\n"
        "       OR t.tank_code = (f.fish_code || '-TANK1')\n"
        "  );\n"
        "SELECT 'fish_instances_v10' AS t, count(*) FROM public.fish_instances_v10;\n"
        "SELECT 'tanks' AS t, count(*) FROM public.tanks;\n"
        "SELECT 'tanks_missing' AS t, count(*)\n"
        "FROM public.fish_instances_v10 f\n"
        "LEFT JOIN public.tanks t ON t.fish_instance_id = f.id\n"
        "WHERE t.id IS NULL;\n"
    )
    psql_stdin(db_url, sql)


def load_legacy_v5(db_url: str) -> None:
    roi_channels_src = newest_snapshot(V5_ROI_CHANNELS_GLOB)
    roi_map_manual_src = newest_snapshot(V5_ROI_PATH_MAP_MANUAL_GLOB)

    print(f"[V5] roi_channels snapshot: {roi_channels_src}")
    print(f"[V5] roi_path_map snapshot: {roi_map_manual_src}")

    if not V5_NORMALIZE_SCRIPT.exists():
        raise SystemExit(f"[STOP] missing v5 normalizer script: {V5_NORMALIZE_SCRIPT}")

    run(["python", str(V5_NORMALIZE_SCRIPT), str(roi_map_manual_src), str(V5_SNAPSHOTS_DIR)])

    if not V5_WIDE_NORM.exists():
        raise SystemExit(f"[STOP] missing normalized file: {V5_WIDE_NORM}")
    if not V5_GENO_NORM.exists():
        raise SystemExit(f"[STOP] missing normalized file: {V5_GENO_NORM}")
    if not V5_TRT_NORM.exists():
        raise SystemExit(f"[STOP] missing normalized file: {V5_TRT_NORM}")

    psql_one(db_url, "TRUNCATE TABLE public.legacy_roi_channels_v5;")
    psql_stdin(
        db_url,
        f"\\copy public.legacy_roi_channels_v5 (roi_path, channel_name, n_tiffs) FROM '{roi_channels_src.as_posix()}' WITH (FORMAT csv, HEADER true);\n"
        "SELECT count(*) AS rows_loaded, count(distinct roi_path) AS roi_paths, count(distinct channel_name) AS channel_names, sum(n_tiffs) AS sum_n_tiffs FROM public.legacy_roi_channels_v5;\n",
    )

    psql_one(db_url, "TRUNCATE TABLE public.legacy_roi_path_map_v5;")
    psql_stdin(
        db_url,
        f"\\copy public.legacy_roi_path_map_v5 (roi_path, date_mount_id, genotype_base_codes, genotype_allele_codes, treatment_rna_base_codes, treatment_plasmid_base_codes) FROM '{roi_map_manual_src.as_posix()}' WITH (FORMAT csv, HEADER true);\n"
        "SELECT count(*) AS rows_loaded, count(distinct roi_path) AS roi_paths FROM public.legacy_roi_path_map_v5;\n",
    )

    psql_stdin(
        db_url,
        "INSERT INTO public.legacy_roi_path_map_v5 (roi_path)\n"
        "SELECT DISTINCT c.roi_path\n"
        "FROM public.legacy_roi_channels_v5 c\n"
        "LEFT JOIN public.legacy_roi_path_map_v5 m USING (roi_path)\n"
        "WHERE m.roi_path IS NULL;\n"
        "DELETE FROM public.legacy_roi_path_map_v5 m\n"
        "WHERE NOT EXISTS (SELECT 1 FROM public.legacy_roi_channels_v5 c WHERE c.roi_path = m.roi_path);\n"
        "SELECT (SELECT count(distinct roi_path) FROM public.legacy_roi_channels_v5) AS roi_paths_channels,\n"
        "       (SELECT count(distinct roi_path) FROM public.legacy_roi_path_map_v5) AS roi_paths_base_map;\n",
    )

    psql_one(db_url, "TRUNCATE TABLE public.legacy_roi_genotype_constructs_v5;")
    psql_one(db_url, "TRUNCATE TABLE public.legacy_roi_treatment_constructs_v5;")
    psql_stdin(
        db_url,
        f"\\copy public.legacy_roi_genotype_constructs_v5 (roi_path, construct_base_code, allele_code) FROM '{V5_GENO_NORM.as_posix()}' WITH (FORMAT csv, HEADER true, FORCE_NOT_NULL (allele_code));\n"
        f"\\copy public.legacy_roi_treatment_constructs_v5 (roi_path, kind, construct_base_code) FROM '{V5_TRT_NORM.as_posix()}' WITH (FORMAT csv, HEADER true);\n"
        "SELECT (SELECT count(*) FROM public.legacy_roi_genotype_constructs_v5) AS genotype_rows_loaded,\n"
        "       (SELECT count(*) FROM public.legacy_roi_treatment_constructs_v5) AS treatment_rows_loaded;\n",
    )

    psql_stdin(
        db_url,
        "WITH g AS (\n"
        "  SELECT lower(btrim(construct_base_code)) AS base_lc\n"
        "  FROM public.legacy_roi_genotype_constructs_v5\n"
        "  WHERE coalesce(btrim(construct_base_code),'') <> ''\n"
        "),\n"
        "u AS (\n"
        "  SELECT g.base_lc, count(*) AS n\n"
        "  FROM g\n"
        "  LEFT JOIN public.constructs c ON lower(c.base_code) = g.base_lc\n"
        "  WHERE c.id IS NULL\n"
        "  GROUP BY g.base_lc\n"
        ")\n"
        "SELECT n, base_lc FROM u ORDER BY n DESC, base_lc LIMIT 100;\n",
    )


def main() -> None:
    require_env("DB_URL")
    db_url = os.environ["DB_URL"]
    print("[DB_URL]", db_url)
    assert_transgene_alleles_exist()

    load_modern_seed_data()
    assert_transgene_alleles_exist()

    ensure_tanks_for_all_fish(db_url)

    load_legacy_v5(db_url)

    print("\n[OK] full local load pipeline completed cleanly")


if __name__ == "__main__":
    main()
