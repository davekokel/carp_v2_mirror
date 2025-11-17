#!/usr/bin/env bash
set -euo pipefail

# decide output dir based on implied flag
if [[ "${SCHEMASPY_FLAGS:-}" == *"-implied"* ]]; then
  OUT_DIR="schema_implied"
  RELNAME="relationships.implied.large"
else
  OUT_DIR="schema_real"
  RELNAME="relationships.real.large"
fi

mkdir -p "$OUT_DIR"

# use Docker (no local Java needed) — replace env vars as appropriate
docker run --rm \
  -v "$PWD/$OUT_DIR:/output" \
  schemaspy/schemaspy:latest \
  -t pgsql -host "$DB_HOST" -port "$DB_PORT" -db "$DB_NAME" \
  -u "$DB_USER" -p "$DB_PASS" \
  -s public -o /output ${SCHEMASPY_FLAGS:-}

echo "✅ Wrote to $OUT_DIR/public"
ls -1 "$OUT_DIR/public/$RELNAME".* 2>/dev/null || true