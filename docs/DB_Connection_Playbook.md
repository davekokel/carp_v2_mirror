# DB Connection Playbook — Quick Start (Updated)

This gets you to a verified working baseline **immediately** for Local, Staging, and Production via the Supabase pooler. It uses copy‑pasteable shell blocks (no inline comments) and verifies each target in order.

## 0) Prereqs
- `psql` on PATH
- Your staging/prod DB passwords handy

## 1) Define DSNs for all three targets

```bash
export LOCAL_DB_URL=${LOCAL_DB_URL:-postgresql://postgres@127.0.0.1:5432/postgres?sslmode=disable}
export STAGING_DB_URL="postgresql://postgres.zebzrvjbalhazztvhhcm@aws-1-us-west-1.pooler.supabase.com:6543/postgres?sslmode=require"
export PROD_DB_URL="postgresql://postgres.gzmbxhkckkspnefpxkgb@aws-0-us-east-2.pooler.supabase.com:6543/postgres?sslmode=require"
printf "LOCAL=%s
STAGING=%s
PROD=%s
" "$LOCAL_DB_URL" "$STAGING_DB_URL" "$PROD_DB_URL"
```

## 2) Configure `~/.pgpass` for pooler hosts (usernames must include the project ref)

```bash
mkdir -p ~/.secrets
touch ~/.pgpass
chmod 600 ~/.pgpass
grep -v aws-1-us-west-1.pooler.supabase.com ~/.pgpass > ~/.pgpass.tmp || true
mv ~/.pgpass.tmp ~/.pgpass
echo "aws-1-us-west-1.pooler.supabase.com:6543:postgres:postgres.zebzrvjbalhazztvhhcm:<YOUR_STAGING_DB_PASSWORD>" >> ~/.pgpass
grep -v aws-0-us-east-2.pooler.supabase.com ~/.pgpass > ~/.pgpass.tmp || true
mv ~/.pgpass.tmp ~/.pgpass
echo "aws-0-us-east-2.pooler.supabase.com:6543:postgres:postgres.gzmbxhkckkspnefpxkgb:<YOUR_PROD_DB_PASSWORD>" >> ~/.pgpass
```

## 3) Verify connectivity and identity for each env

```bash
psql "$LOCAL_DB_URL"   -Atc "select inet_server_addr(), current_database(), current_user"
psql "$STAGING_DB_URL" -Atc "select inet_server_addr(), current_database(), current_user"
psql "$PROD_DB_URL"    -Atc "select inet_server_addr(), current_database(), current_user"
```

## 4) Confirm connection behavior parity (SSL, timezone, search_path)

```bash
psql "$LOCAL_DB_URL"   -Atc "show ssl; show TimeZone; show search_path"
psql "$STAGING_DB_URL" -Atc "show ssl; show TimeZone; show search_path"
psql "$PROD_DB_URL"    -Atc "show ssl; show TimeZone; show search_path"
```

## 5) Optional helpers to switch app `DB_URL` quickly

```bash
use_local() { export DB_URL="$LOCAL_DB_URL"; printf "DB_URL=%s
" "$DB_URL"; }
use_staging() { export DB_URL="$STAGING_DB_URL"; printf "DB_URL=%s
" "$DB_URL"; }
use_prod() { export DB_URL="$PROD_DB_URL"; printf "DB_URL=%s
" "$DB_URL"; }
```

## 6) Quick schema smoke checks (version, extensions)

```bash
psql "$LOCAL_DB_URL"   -Atc "select version(); select extname, extversion from pg_extension order by 1"
psql "$STAGING_DB_URL" -Atc "select version(); select extname, extversion from pg_extension order by 1"
psql "$PROD_DB_URL"    -Atc "select version(); select extname, extversion from pg_extension order by 1"
```

## 7) Fast data spot checks

```bash
psql "$LOCAL_DB_URL"   -Atc "select 'fish' t, count(*) from public.fish union all select 'transgenes', count(*) from public.transgenes union all select 'transgene_alleles', count(*) from public.transgene_alleles"
psql "$STAGING_DB_URL" -Atc "select 'fish' t, count(*) from public.fish union all select 'transgenes', count(*) from public.transgenes union all select 'transgene_alleles', count(*) from public.transgene_alleles"
psql "$PROD_DB_URL"    -Atc "select 'fish' t, count(*) from public.fish union all select 'transgenes', count(*) from public.transgenes union all select 'transgene_alleles', count(*) from public.transgene_alleles"
```

## Troubleshooting quick hits

**Error:** `FATAL: Tenant or user not found`  
**Fix:** Ensure the pooler username includes the project ref and matches the host region.
- Username format: `postgres.<project-ref>`
- Pooler host format: `aws-<cluster>-<region>.pooler.supabase.com`
- Port: `6543`

**Direct (non‑pooler) test**

```bash
psql "postgresql://postgres@gzmbxhkckkspnefpxkgb.supabase.co:5432/postgres?sslmode=require" -Atc "select version(), current_user"
```

If the direct test works but the pooler fails, re‑check the pooler host, port 6543, and the `~/.pgpass` username line for a typo in the `<project-ref>`.
