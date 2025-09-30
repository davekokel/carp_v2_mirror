# Devcontainer DB Notes

- Inside Docker/devcontainers, use the **Supabase connection pooler** (IPv4), not the direct DB host (often IPv6-only).
- Username must be **project-qualified**: `<db_user>.<project_ref>`
- Some libpq/psql builds need `channel_binding=disable` with the pooler.

## Example `.streamlit/secrets.toml` (staging, read-only)
```toml
DB_URL = "host=aws-1-us-west-1.pooler.supabase.com port=6543 dbname=postgres user=teammate_ro.<PROJECT_REF> password=<PW> sslmode=require channel_binding=disable"
SUPABASE_URL = "https://<PROJECT_REF>.supabase.co"
SUPABASE_ANON_KEY = "<ANON-KEY>"
APP_PASSWORD = "letmein"
READ_ONLY = "true"
