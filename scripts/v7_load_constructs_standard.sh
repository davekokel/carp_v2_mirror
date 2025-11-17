#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

. .venv/bin/activate
. scripts/use_db.sh
use_local

python scripts/v7_load_constructs_from_csv.py \
  --plasmids carp_app/seed_kits/2025-11-15-121231-autoload/plasmids.csv \
  --rnas carp_app/seed_kits/2025-11-15-121231-autoload/rnas.csv \
  --dyes carp_app/seed_kits/2025-11-15-121231-autoload/dyes.csv
