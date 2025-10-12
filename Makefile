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

# Ship code to mirror staging (Streamlit staging redeploys)
pub-staging:
	@git push mirror origin/main:staging

# Promote to prod (requires ALLOW_PROD=1)
pub-prod:
	@[ "$$ALLOW_PROD" = "1" ] || (echo "Refusing: set ALLOW_PROD=1 to promote"; exit 1)
	@git push mirror origin/main:prod

# publish current commit (HEAD) to mirror
pub-staging:
	@git push mirror HEAD:staging

pub-prod:
	@[ "$$ALLOW_PROD" = "1" ] || (echo "Refusing: set ALLOW_PROD=1 to promote"; exit 1)
	@git push mirror HEAD:prod
