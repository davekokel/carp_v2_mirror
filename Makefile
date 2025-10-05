# =========================
# CARP Makefile (full)
# =========================

SHELL := /bin/bash

# ---- DB URLs / Paths ----
LOCAL_DB_URL    ?= postgresql://postgres@127.0.0.1:5432/postgres?sslmode=disable
MIG_DIR         := supabase/migrations
BASH            ?= /opt/homebrew/bin/bash

# =========================
# Existing targets (kept)
# =========================

reset:
	@supabase db reset --local --yes

check:
	@$(BASH) ./scripts/check_sequences.sh

# Push to the project you linked in this repo (carp_v2)
deploy-linked:
	@supabase db push --linked

# If you prefer a URL-based push (set STAGING_DB_URL first)
deploy-url:
	@supabase db push --db-url "$$STAGING_DB_URL"

# =========================
# New: parity / migration helpers
# =========================

.PHONY: migrate-local migrate-docker migrate-url parity local-cleanseed docker-baseline

# Apply ALL repo migrations to Homebrew (127.0.0.1:5432)
migrate-local:
	@for f in $(MIG_DIR)/*.sql ; do \
		echo "Applying $$f -> LOCAL"; \
		psql "$(LOCAL_DB_URL)" -v ON_ERROR_STOP=1 -f "$$f" || exit 1 ; \
	done
	@echo "✅ migrate-local done"

# Recreate Docker (Supabase local stack) and apply all migrations
# Uses supabase CLI reset which replays migrations into the container DB.
migrate-docker:
	@supabase db reset --local --yes
	@echo "✅ migrate-docker done"

# Generic: MIGRATE_URL="postgresql://user:pass@host:port/db?sslmode=..."
migrate-url:
	@if [ -z "$$MIGRATE_URL" ]; then echo "Set MIGRATE_URL first"; exit 1; fi
	@for f in $(MIG_DIR)/*.sql ; do \
		echo "Applying $$f -> $$MIGRATE_URL"; \
		psql "$$MIGRATE_URL" -v ON_ERROR_STOP=1 -f "$$f" || exit 1 ; \
	done
	@echo "✅ migrate-url done"

# Keep LOCAL (Homebrew) and DOCKER (Supabase) in sync in one go
parity:
	@$(MAKE) migrate-local && $(MAKE) migrate-docker
	@echo "✅ Parity applied: LOCAL (Homebrew) and DOCKER (Supabase) now share the same migrations."

# Wipe Homebrew data, apply latest baseline, start app pointed at Homebrew
local-cleanseed:
	# wipe data (keeps roles/extensions)
	@psql "$(LOCAL_DB_URL)" -v ON_ERROR_STOP=1 <<'SQL'
BEGIN;
DO $$
DECLARE stmt text;
BEGIN
  SELECT 'TRUNCATE TABLE '||string_agg(format('%I.%I',schemaname,tablename),', ')||' RESTART IDENTITY CASCADE'
  INTO stmt FROM pg_tables WHERE schemaname='public';
  IF stmt IS NOT NULL THEN EXECUTE stmt; END IF;
END$$;
COMMIT;
SQL
	# apply baseline (last *_baseline_schema.sql)
	@psql "$(LOCAL_DB_URL)" -v ON_ERROR_STOP=1 -f $$(ls -1 supabase/migrations/*_baseline_schema.sql | tail -n1)
	# start app on Homebrew
	@echo "Starting app on Homebrew…"
	@DB_URL="$(LOCAL_DB_URL)" APP_FORCE_LOCAL=1 scripts/carp_local_start

# (Optional) baseline-only reset for Docker
docker-baseline:
	@supabase db reset --local --yes
	@psql "postgresql://postgres:postgres@127.0.0.1:54322/postgres?sslmode=disable" -v ON_ERROR_STOP=1 \
	  -f $$(ls -1 supabase/migrations/*_baseline_schema.sql | tail -n1)
	@echo "✅ Docker baseline applied"
PYTHON ?= python3

guard-migrations:
	@$(PYTHON) scripts/guard_migration.py supabase/migrations

# --- local dev helpers ---
DB_URL_LOCAL := $(shell scripts/dburl_local.sh)


# --- local dev helpers ---
DB_URL_LOCAL := $(shell scripts/dburl_local.sh)

smoke:
	@psql -d "$(DB_URL_LOCAL)" -Atc "select 'tables',count(*) from information_schema.tables where table_schema='public' and table_type='BASE TABLE' union all select 'views',count(*) from information_schema.views where table_schema='public' order by 1"

run-local:
	@export DB_URL="$(DB_URL_LOCAL)" PYTHONPATH=$$(pwd)/supabase/ui:$$PYTHONPATH; \
	python3 -m venv .venv 2>/dev/null || true; . .venv/bin/activate; \
	pip install -r supabase/ui/requirements.txt >/dev/null; \
	mkdir -p .streamlit; printf 'APP_LOCKED = false\n' > .streamlit/secrets.toml; \
	streamlit run supabase/ui/streamlit_app.py --server.address 0.0.0.0 --server.port 8501
