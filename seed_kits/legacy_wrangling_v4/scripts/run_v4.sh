#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python scripts/01_link_v4.py
python scripts/02_enrich_v4.py
python scripts/03_qc_v4.py
