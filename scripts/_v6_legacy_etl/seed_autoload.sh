#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [ -z "${DB_URL:-}" ]; then
  echo "DB_URL is not set (did you run use_local/use_staging?)" >&2
  exit 1
fi

SEED_DIR="${1:-$ROOT/seed_kits/2025-11-15-121231-autoload}"

python - <<PY
from pathlib import Path
from carp_app.ui.lib.seed_autoload import autoload_seed_kit

autoload_seed_kit(Path("${SEED_DIR}"), dry_run=False)
PY
