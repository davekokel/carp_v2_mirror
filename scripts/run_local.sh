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
  DB_URL="${LOCAL_DB_URL}" PYTHONPATH="$(pwd)" \
  APP_COMMIT=103df8d streamlit run "carp_app/ui/pages/000_👋_welcome.py"
