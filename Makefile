reset:
	@supabase db reset --local --yes

smoke:
	@psql -Atc "select 'tables',count(*) from information_schema.tables where table_schema='public' and table_type='BASE TABLE'
	union all select 'views',count(*) from information_schema.views where table_schema='public' order by 1"

check:
	@/opt/homebrew/bin/bash ./scripts/check_sequences.sh

# Push to the project you linked in this repo (carp_v2)
deploy-linked:
	@supabase db push --linked

# If you prefer a URL-based push (set STAGING_DB_URL first)
deploy-url:
	@supabase db push --db-url "$$STAGING_DB_URL"
