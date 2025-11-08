#!/usr/bin/env bash
set -euo pipefail

# -----------------------
# Config (overridable via env)
# -----------------------
OUT_DIR="${1:-schema_report}"       # output folder
MODE="${MODE:-real}"                # real | implied
SCHEMAS="${SCHEMAS:-public}"        # e.g. "public,raw"
INCLUDE_VIEWS="${INCLUDE_VIEWS:-0}" # 0 = tables only, 1 = include views

# DB connection (local defaults)
DB_HOST="${DB_HOST:-host.docker.internal}"
DB_PORT="${DB_PORT:-54322}"
DB_NAME="${DB_NAME:-postgres}"
DB_USER="${DB_USER:-schemaspy}"
DB_PASS="${DB_PASS:-diagram_only_pw}"

mkdir -p "$OUT_DIR"

# SchemaSpy relationship switches
# - real: only declared FKs (add -noimplied)
# - implied: keep inferred links (no -noimplied)
EXTRA_OPTS=()
if [[ "$MODE" == "real" ]]; then
  EXTRA_OPTS+=(-noimplied)
fi

# Hide orphans to reduce noise
EXTRA_OPTS+=(-noorphan)

# Exclude views unless explicitly enabled
if [[ "$INCLUDE_VIEWS" == "0" ]]; then
  EXTRA_OPTS+=(-noviews)
fi

# Run SchemaSpy (Docker image ships with PG driver)
docker run --rm \
  -e JAVA_TOOL_OPTIONS="-Djava.awt.headless=true" \
  -v "$PWD/$OUT_DIR:/output" \
  schemaspy/schemaspy:latest \
  -t pgsql \
  -host "$DB_HOST" \
  -port "$DB_PORT" \
  -db "$DB_NAME" \
  -u "$DB_USER" \
  ${DB_PASS:+-p "$DB_PASS"} \
  -schemas "$SCHEMAS" \
  -hq -norows "${EXTRA_OPTS[@]}"

echo "✅ Wrote $OUT_DIR/index.html"

# Auto-open on macOS/Linux
if command -v open >/dev/null 2>&1; then
  open "$OUT_DIR/index.html" || true
elif command v xdg-open >/dev/null 2>&1; then
  xdg-open "$OUT_DIR/index.html" || true
fi
