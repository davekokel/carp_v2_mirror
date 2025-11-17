#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

. .venv/bin/activate
. scripts/use_db.sh
use_local

LEGACY_STD_DIR="seed_kits/standard_from_legacy"

python scripts/v7_load_constructs_from_csv.py \
  --plasmids "$LEGACY_STD_DIR/plasmids_standard_from_legacy.csv" \
  --rnas "$LEGACY_STD_DIR/rnas_standard_from_legacy.csv" \
  --dyes "$LEGACY_STD_DIR/dyes_from_legacy_rna.csv"
