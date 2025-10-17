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

H="db.zebzrvjbalhazztvhhcm.supabase.co"
P="5432"
D="postgres"
U="postgres"

PW="$(awk -F: -v h="$H" -v p="$P" -v d="$D" -v u="$U" '$1==h && $2==p && $3==d && $4==u {print $5; exit}' ~/.pgpass)"
[ -n "$PW" ] || { echo "ERROR: no matching line in ~/.pgpass for $H:$P:$D:$U"; exit 1; }

EPW="$(python -c 'import sys, urllib.parse; print(urllib.parse.quote(sys.argv[1], safe=""))' "$PW")"

export DB_URL="postgresql://${U}:${EPW}@${H}:${P}/${D}?sslmode=require"

env -u PGUSER -u PGPASSWORD -u PGHOST -u PGPORT -u PGDATABASE \
  PYTHONPATH="$(pwd)" \
  APP_COMMIT=f9d2489 streamlit run "supabase/ui/streamlit_app.py"
