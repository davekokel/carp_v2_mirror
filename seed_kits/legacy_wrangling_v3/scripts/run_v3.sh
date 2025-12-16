#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python scripts/01_link.py
python scripts/02_enrich.py
python scripts/03_qc.py
