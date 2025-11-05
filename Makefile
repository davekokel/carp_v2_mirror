.PHONY: app-local app-staging app-prod
app-local:
	. scripts/use_db.sh && use_local && python -m streamlit run carp_app/ui/streamlit_app.py
app-staging:
	if [ -f .env.staging.direct ]; then \
		set -a; . .env.staging.direct; set +a; \
	else \
		. scripts/use_db.sh && use_staging; \
	fi; \
	echo "$$DB_URL"; \
	python -m streamlit run carp_app/ui/streamlit_app.py
app-prod:
	. scripts/use_db.sh && use_prod && python -m streamlit run carp_app/ui/streamlit_app.py

.PHONY: run-staging-direct run-staging-pooler
run-staging-direct:
	./scripts/run_staging_direct.sh

run-staging-pooler:
	./scripts/run_staging_pooler.sh


.PHONY: run-local
run-local:
	./scripts/run_local.sh

seed_ft_demo:
	psql "$$DB_URL" -v ON_ERROR_STOP=1 -f supabase/seeds/local/ft_demo.seed.sql
