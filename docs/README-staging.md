# Staging (Read-Only) Setup

Use a read-only DB user for staging. Do **not** use the owner password.

## 1) .streamlit/secrets.toml (staging)
```toml
DB_URL = "postgresql://teammate_ro:<PASSWORD>@db.<PROJECT-REF>.supabase.co:5432/postgres?sslmode=require"
SUPABASE_URL = "https://<PROJECT-REF>.supabase.co"
SUPABASE_ANON_KEY = "<ANON-KEY>"
APP_PASSWORD = "letmein"
READ_ONLY = "true"
```

## 2) Test connection
```bash
psql "$DB_URL" -Atc "select now(), current_user, current_database();"
```

## 3) Run UI
```bash
export PYTHONPATH=$PWD/supabase/ui:$PYTHONPATH
python -m streamlit run supabase/ui/streamlit_app.py
```

Keep real passwords out of Git. Share DSNs privately (1Password/Slack DM).
