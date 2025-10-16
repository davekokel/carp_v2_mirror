#!/usr/bin/env bash
set -euo pipefail
export PGCONNECT_TIMEOUT=${PGCONNECT_TIMEOUT:-5}

export LOCAL_DB_URL=${LOCAL_DB_URL:-postgresql://postgres@127.0.0.1:5432/postgres?sslmode=disable}
export STAGING_REF="zebzrvjbalhazztvhhcm"
export STAGING_POOLER_HOST="aws-1-us-west-1.pooler.supabase.com"
export STAGING_DB_URL="postgresql://postgres.${STAGING_REF}@${STAGING_POOLER_HOST}:6543/postgres?sslmode=require"
export PROD_REF="gzmbxhkckkspnefpxkgb"
export PROD_POOLER_HOST="aws-1-us-east-2.pooler.supabase.com"
export PROD_DIRECT_HOST="db.${PROD_REF}.supabase.co"
export PROD_DB_URL="postgresql://postgres.${PROD_REF}@${PROD_POOLER_HOST}:6543/postgres?sslmode=require"

printf "LOCAL=%s
STAGING=%s
PROD=%s
" "$LOCAL_DB_URL" "$STAGING_DB_URL" "$PROD_DB_URL"

mkdir -p ~/.secrets
touch ~/.pgpass
chmod 600 ~/.pgpass

need_staging=0
need_prod=0

grep -q "^${STAGING_POOLER_HOST}:6543:postgres:postgres.${STAGING_REF}:" ~/.pgpass || need_staging=1
grep -q "^${PROD_POOLER_HOST}:6543:postgres:postgres.${PROD_REF}:" ~/.pgpass || need_prod=1

if [ "$need_staging" -eq 1 ] || [ "$need_prod" -eq 1 ]; then
  echo "PGPASS_CHECK=MISSING_ENTRIES"
  if [ "$need_staging" -eq 1 ]; then
    echo "ADD_TO_PGPASS=${STAGING_POOLER_HOST}:6543:postgres:postgres.${STAGING_REF}:<YOUR_STAGING_DB_PASSWORD>"
  fi
  if [ "$need_prod" -eq 1 ]; then
    echo "ADD_TO_PGPASS=${PROD_POOLER_HOST}:6543:postgres:postgres.${PROD_REF}:<YOUR_PROD_DB_PASSWORD>"
  fi
else
  echo "PGPASS_CHECK=OK"
fi

run_psql() {
  local name="$1"
  local url="$2"
  if psql "$url" -w -Atc "select inet_server_addr(), current_database(), current_user" >/tmp/_${name}_id.txt 2>/tmp/_${name}_err.txt; then
    printf "%s=PASS %s
" "$name" "$(cat /tmp/_${name}_id.txt)"
  else
    printf "%s=FAIL %s
" "$name" "$(tr -d '
' </tmp/_${name}_err.txt)"
  fi
}

run_psql LOCAL "$LOCAL_DB_URL"
run_psql STAGING "$STAGING_DB_URL"
run_psql PROD_POOLER "$PROD_DB_URL"
run_psql PROD_DIRECT "postgresql://postgres@${PROD_DIRECT_HOST}:5432/postgres?sslmode=require"
