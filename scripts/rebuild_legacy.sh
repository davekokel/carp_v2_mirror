#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [ $# -lt 1 ]; then
  echo "Usage:" >&2
  echo "  scripts/rebuild_legacy.sh TIMESTAMP" >&2
  echo "  scripts/rebuild_legacy.sh DIR TIMESTAMP" >&2
  echo "Where TIMESTAMP matches filenames like local_legacy_pairs_YYYYMMDD_HHMMSS.csv" >&2
  exit 1
fi

if [ -d "$1" ]; then
  DIR="$1"
  TS="${2:-}"
  if [ -z "$TS" ]; then
    echo "Error: when specifying a directory, you must also supply a timestamp." >&2
    exit 1
  fi
else
  DIR="supabase/snapshots"
  TS="$1"
fi

PAIRS="$DIR/local_legacy_pairs_${TS}.csv"
CLUTCHES="$DIR/local_legacy_clutches_${TS}.csv"
ROIS="$DIR/local_legacy_imaging_rois_${TS}.csv"

missing=0
for f in "$PAIRS" "$CLUTCHES" "$ROIS"; do
  if [ ! -f "$f" ]; then
    echo "Missing CSV: $f" >&2
    missing=1
  fi
done

if [ "$missing" -ne 0 ]; then
  echo "Missing one or more CSVs for timestamp ${TS}" >&2
  echo "Expected in directory: ${DIR}" >&2
  echo "  $PAIRS" >&2
  echo "  $CLUTCHES" >&2
  echo "  $ROIS" >&2
  exit 1
fi

if [ -z "${DB_URL:-}" ]; then
  echo "Error: DB_URL is not set. Did you run use_local/use_staging/use_prod?" >&2
  exit 1
fi

# Check that legacy tables exist before we try to truncate/copy
tables_missing=()
for t in legacy_pairs legacy_clutches imaging_rois; do
  exists=$(psql "$DB_URL" -Atc "SELECT to_regclass('public.$t')" || echo "")
  if [ -z "$exists" ] || [ "$exists" = "" ]; then
    tables_missing+=("$t")
  fi
done

if [ ${#tables_missing[@]} -ne 0 ]; then
  echo "Legacy tables missing in DB; cannot rebuild legacy:" >&2
  printf '  %s\n' "${tables_missing[@]}" >&2
  echo "Make sure migrations that create these tables have been applied before running rebuild_legacy." >&2
  exit 1
fi

psql "$DB_URL" <<SQL
BEGIN;

TRUNCATE TABLE public.imaging_rois RESTART IDENTITY CASCADE;
TRUNCATE TABLE public.legacy_clutches RESTART IDENTITY CASCADE;
TRUNCATE TABLE public.legacy_pairs RESTART IDENTITY CASCADE;

-- reload pairs & clutches directly
\COPY public.legacy_pairs    FROM '${PAIRS}'    CSV HEADER;
\COPY public.legacy_clutches FROM '${CLUTCHES}' CSV HEADER;

-- temp import table for imaging_rois to match CSV header exactly
DROP TABLE IF EXISTS public._legacy_imaging_rois_import;

CREATE TABLE public._legacy_imaging_rois_import (
  imaging_roi_id uuid,
  fish_id uuid,
  fish_label text,
  roi_index integer,
  roi_name text,
  roi_dir text,
  dataset text,
  experiment_name text,
  data_location text,
  mount_row_index_scored integer,
  mount_id text,
  date_experiment text,
  date_mount text,
  raw_id uuid,
  legacy_pair_id uuid,
  legacy_clutch_id uuid,
  zf_female_genotype text,
  zf_male_genotype text,
  additional_plasmids_injected text,
  additional_mrnas_injected text,
  additonal_proteins_injected text,
  additonal_dye_and_chemicals text,
  date_born text,
  time_mounted text,
  mounting_orientation text,
  date_screened_initial_feedback text,
  date_imaged text
);

\COPY public._legacy_imaging_rois_import FROM '${ROIS}' CSV HEADER;

INSERT INTO public.imaging_rois (
  id,
  fish_id,
  fish_label,
  roi_index,
  roi_name,
  roi_dir,
  dataset,
  experiment_name,
  data_location,
  mount_row_index_scored,
  mount_id,
  date_experiment,
  date_mount,
  raw_id,
  zf_female_genotype,
  zf_male_genotype,
  additional_plasmids_injected,
  additional_mrnas_injected,
  additonal_proteins_injected,
  additonal_dye_and_chemicals,
  date_born,
  time_mounted,
  mounting_orientation,
  date_screened_initial_feedback,
  date_imaged
)
SELECT
  imaging_roi_id AS id,
  fish_id,
  fish_label,
  roi_index,
  roi_name,
  roi_dir,
  dataset,
  experiment_name,
  data_location,
  mount_row_index_scored,
  mount_id,
  date_experiment,
  date_mount,
  raw_id,
  zf_female_genotype,
  zf_male_genotype,
  additional_plasmids_injected,
  additional_mrnas_injected,
  additonal_proteins_injected,
  additonal_dye_and_chemicals,
  date_born,
  time_mounted,
  mounting_orientation,
  date_screened_initial_feedback,
  date_imaged
FROM public._legacy_imaging_rois_import;

DROP TABLE public._legacy_imaging_rois_import;

COMMIT;
SQL

echo "Legacy rebuild complete:"
psql "$DB_URL" -Atc "
  SELECT 'legacy_pairs' AS table, COUNT(*) FROM public.legacy_pairs
  UNION ALL
  SELECT 'legacy_clutches', COUNT(*) FROM public.legacy_clutches
  UNION ALL
  SELECT 'imaging_rois' AS table, COUNT(*) FROM public.imaging_rois;
"
