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

health-prod:
	@set -a; . ./.env.prod.direct; set +a; psql "$$DB_URL" -Atc "select current_user, current_database(), inet_server_addr()::text, inet_server_port()"

health-prod-ro:
	@set -a; . ./.env.prod.ro; set +a; psql "$$DB_URL" -Atc "select current_user, current_database(), inet_server_addr()::text, inet_server_port()"

run-staging:
	@./scripts/run_staging_direct_clean.sh
run-prod-ro:
	@./scripts/run_prod_ro_direct_clean.sh
