.PHONY: app-staging-pgpass app-prod-pgpass
APP ?= carp_app/ui/streamlit_app.py
PY  ?= .venv/bin/python
POOL ?= aws-1-us-west-1.pooler.supabase.com
STAGING_ID ?= zebzrvjbalhazztvhhcm
PROD_ID    ?= gzmbxhkckkspnefpxkgb

app-staging-pgpass:
	@PROJ="$(STAGING_ID)"; \
	PW="$$(awk -F: -v U="postgres.$$PROJ" '$$1=="$(POOL)" && $$2=="6543" && $$3=="postgres" && $$4==U{print $$5;exit}' $$HOME/.pgpass)"; \
	[ -n "$$PW" ] || { echo "No pgpass entry for staging"; exit 2; }; \
	ENCPW="$$(PW="$$PW" python -c 'import os,urllib.parse;print(urllib.parse.quote(os.environ["PW"]))')"; \
	env -u PGHOST -u PGPORT -u PGUSER -u PGPASSWORD -u DATABASE_URL \
	DB_URL="postgresql://postgres.$$PROJ:$${ENCPW}@$(POOL):6543/postgres?sslmode=require" \
	$(PY) -m streamlit run "$(APP)"

app-prod-pgpass:
	@PROJ="$(PROD_ID)"; \
	PW="$$(awk -F: -v U="postgres.$$PROJ" '$$1=="$(POOL)" && $$2=="6543" && $$3=="postgres" && $$4==U{print $$5;exit}' $$HOME/.pgpass)"; \
	[ -n "$$PW" ] || { echo "No pgpass entry for prod"; exit 2; }; \
	ENCPW="$$(PW="$$PW" python -c 'import os,urllib.parse;print(urllib.parse.quote(os.environ["PW"]))')"; \
	env -u PGHOST -u PGPORT -u PGUSER -u PGPASSWORD -u DATABASE_URL \
	DB_URL="postgresql://postgres.$$PROJ:$${ENCPW}@$(POOL):6543/postgres?sslmode=require" \
	$(PY) -m streamlit run "$(APP)"
.PHONY: deploy-staging promote-prod parity
deploy-staging:
	@git push org_mirror main:staging

promote-prod:
	@SHA=$$(git rev-parse org_mirror/staging); git push -f org_mirror $$SHA:refs/heads/prod

parity:
	@git rev-parse --short org_mirror/staging
	@git rev-parse --short org_mirror/prod
	@git diff --name-status org_mirror/staging..org_mirror/prod
