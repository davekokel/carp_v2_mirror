#!/usr/bin/env bash
set -euo pipefail

PORT=54322
DB=carp_rebuild
USER=postgres
HOST=127.0.0.1
DB_URL="postgresql://$USER@$HOST:$PORT/$DB?sslmode=disable"
export DB_URL

echo "🚧 Rebuilding local database: $DB_URL"

dropdb --if-exists -h "$HOST" -p "$PORT" -U "$USER" "$DB"
createdb -h "$HOST" -p "$PORT" -U "$USER" "$DB"

echo "📜 Applying migrations..."
./scripts/apply_migrations.sh

echo "🔍 Checking schema conventions..."
psql "$DB_URL" -Atc "table public.v_conventions_checks" || echo "⚠️ conventions check view missing"

echo "✅ Local rebuild complete."
