rebuild-local:
	@psql "$$DB_URL" -v ON_ERROR_STOP=1 -c "DROP SCHEMA IF EXISTS public CASCADE; CREATE SCHEMA IF NOT EXISTS public;"
	@psql "$$DB_URL" -v ON_ERROR_STOP=1 -f supabase/migrations/00000000_baseline_v2.sql
	@psql "$$DB_URL" -Atc "select 'tables',count(*) from information_schema.tables where table_schema='public';"

smoke:
	@psql "$$DB_URL" -Atc "select 'has_fish_cols', count(*) from information_schema.columns where table_schema='public' and table_name='fish';"
	@psql "$$DB_URL" -Atc "select 'has_containers_cols', count(*) from information_schema.columns where table_schema='public' and table_name='containers';"
	@echo "✅ smoke ok"

smoke:
	@psql "$$DB_URL" -Atc "select 'has_fish_cols', count(*) from information_schema.columns where table_schema='public' and table_name='fish';"
	@psql "$$DB_URL" -Atc "select 'has_containers_cols', count(*) from information_schema.columns where table_schema='public' and table_name='containers';"
	@echo "✅ smoke ok"

guard-migrations:
	@ls -1 supabase/migrations/*.sql | awk '!/^[0-9]{8}_[0-9]{6}_.+\.sql$$/ {print "Bad name:", $$0; bad=1} END{exit bad}'

verify-id-only:
	@psql "$$DB_URL" -v ON_ERROR_STOP=1 -f scripts/verify_id_only.sql

