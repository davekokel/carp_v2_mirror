#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

TS="${1:-}"

if [ -z "$TS" ]; then
  TS=$(ls -1 supabase/snapshots/local_legacy_pairs_*.csv 2>/dev/null | sed 's/.*local_legacy_pairs_//' | sed 's/.csv$//' | sort | tail -n 1 || true)
fi

if [ -z "$TS" ]; then
  echo "No legacy snapshot found in supabase/snapshots" >&2
  exit 1
fi

PAIRS="supabase/snapshots/local_legacy_pairs_${TS}.csv"
CLUTCHES="supabase/snapshots/local_legacy_clutches_${TS}.csv"
ROIS="supabase/snapshots/local_legacy_imaging_rois_${TS}.csv"

if [ ! -f "$PAIRS" ] || [ ! -f "$CLUTCHES" ] || [ ! -f "$ROIS" ]; then
  echo "Missing one or more CSVs for timestamp $TS" >&2
  echo "Expected:" >&2
  echo "  $PAIRS" >&2
  echo "  $CLUTCHES" >&2
  echo "  $ROIS" >&2
  exit 1
fi

psql "$DB_URL" <<SQL
TRUNCATE TABLE public.imaging_rois RESTART IDENTITY CASCADE;
TRUNCATE TABLE public.legacy_clutches RESTART IDENTITY CASCADE;
TRUNCATE TABLE public.legacy_pairs RESTART IDENTITY CASCADE;

\COPY public.legacy_pairs (id,dataset,zf_female_genotype,zf_male_genotype,pair_code,created_at) FROM '$PAIRS' CSV HEADER;
\COPY public.legacy_clutches (id,legacy_pair_id,dataset,date_mount,clutch_code,created_at) FROM '$CLUTCHES' CSV HEADER;
\COPY public.imaging_rois (id,fish_id,fish_label,roi_index,roi_name,roi_dir,dataset,experiment_name,data_location,mount_row_index_scored,mount_id,date_experiment,date_mount,raw_id,legacy_pair_id,legacy_clutch_id,zf_female_genotype,zf_male_genotype,additional_plasmids_injected,additional_mrnas_injected,additonal_proteins_injected,additonal_dye_and_chemicals,date_born,time_mounted,mounting_orientation,date_screened_initial_feedback,date_imaged) FROM '$ROIS' CSV HEADER;
SQL
