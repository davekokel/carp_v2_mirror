DB_URL_LOCAL := $(shell scripts/dburl_local.sh)

.PHONY: smoke-local run-local

smoke-local:
	@psql -d "$(DB_URL_LOCAL)" -Atc "select 'tables',count(*) from information_schema.tables where table_schema='public' and table_type='BASE TABLE' union all select 'views',count(*) from information_schema.views where table_schema='public' order by 1"

run-local:
	@export DB_URL="$(DB_URL_LOCAL)" PYTHONPATH=$$(pwd)/supabase/ui:$$PYTHONPATH; \
	python3 -m venv .venv 2>/dev/null || true; . .venv/bin/activate; \
	pip install -r supabase/ui/requirements.txt >/dev/null; \
	mkdir -p .streamlit; printf 'APP_LOCKED = false\n' > .streamlit/secrets.toml; \
	streamlit run supabase/ui/streamlit_app.py --server.address 0.0.0.0 --server.port 8501
