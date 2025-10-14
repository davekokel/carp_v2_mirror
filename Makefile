rebuild-local:
	@psql "$$DB_URL" -v ON_ERROR_STOP=1 -c "DROP SCHEMA IF EXISTS public CASCADE; CREATE SCHEMA IF NOT EXISTS public;"
	@psql "$$DB_URL" -v ON_ERROR_STOP=1 -f supabase/migrations/00000000_baseline_v2.sql
	@psql "$$DB_URL" -Atc "select 'tables',count(*) from information_schema.tables where table_schema='public';"
