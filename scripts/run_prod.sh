# inject APP_COMMIT from git
# inject APP_COMMIT from git
# inject APP_COMMIT from git
# inject APP_COMMIT from git
# inject APP_COMMIT from git
# inject APP_COMMIT from git
# inject APP_COMMIT from git
# inject APP_COMMIT from git
# inject APP_COMMIT from git
# inject APP_COMMIT from git
#!/usr/bin/env bash
set -euo pipefail
env -u PGUSER -u PGPASSWORD -u PGHOST -u PGPORT -u PGDATABASE \
  DB_URL="${PROD_DB_URL}" PYTHONPATH="$(pwd)" \
  APP_COMMIT=103df8d APP_COMMIT=f9d2489 streamlit run carp_app/ui/streamlit_app.py
