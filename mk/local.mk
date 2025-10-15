-include .env.local
export PYTHONPATH:=$(shell pwd)

run-local:
	. .venv/bin/activate && \
	AUTH_MODE=off DB_URL="$$(supabase status -o env 2>/dev/null | sed -n 's/^DATABASE_URL=//p' | tr -d '\r')" : $${DB_URL:=postgresql://postgres@127.0.0.1:5432/postgres?sslmode=disable} && \
	python -m streamlit run carp_app/ui/streamlit_app.py --server.port 8501

run-staging:
	. .venv/bin/activate && \
	AUTH_MODE=passcode PASSCODE=$${PASSCODE} DB_URL="postgresql://postgres.$${STAGING_PROJECT_ID}@aws-1-us-west-1.pooler.supabase.com:6543/postgres?sslmode=require" && \
	python -m streamlit run carp_app/ui/streamlit_app.py --server.port 8502

run-prod:
	. .venv/bin/activate && \
	unset AUTH_MODE && DB_URL="postgresql://postgres.$${PROD_PROJECT_ID}@<your-prod-pooler-host>:<port>/postgres?sslmode=require" && \
	python -m streamlit run carp_app/ui/streamlit_app.py --server.port 8503
