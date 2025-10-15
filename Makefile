.PHONY: app-local app-staging
APP ?= supabase/ui/streamlit_app.py
PY  ?= .venv/bin/python

app-local:
\t@env -u PGHOST -u PGPORT -u PGUSER -u PGPASSWORD -u DATABASE_URL DB_URL="postgresql://postgres@127.0.0.1:5432/postgres?sslmode=disable" $(PY) -m streamlit run "$(APP)"

app-staging:
\t@env -u PGHOST -u PGPORT -u PGUSER -u PGPASSWORD -u DATABASE_URL DB_URL="postgresql://postgres.zebzrvjbalhazztvhhcm@aws-1-us-west-1.pooler.supabase.com:6543/postgres?sslmode=require" $(PY) -m streamlit run "$(APP)"
