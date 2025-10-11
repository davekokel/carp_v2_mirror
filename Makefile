.PHONY: run-staging staging-start run-staging-direct

run-staging:
	@set -a; . ./.env.staging; set +a; \
	.venv/bin/streamlit run supabase/ui/streamlit_app.py

staging-start: run-staging

run-staging-direct:
	@set -a; . ./.env.staging.direct; set +a; \
	.venv/bin/streamlit run supabase/ui/streamlit_app.py
# ==== Targets ====

health-staging:
	@./scripts/db_healthcheck.py
