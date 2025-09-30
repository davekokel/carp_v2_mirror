## Deploy to Streamlit Cloud

1. Repo: use the mirror repo `davekokel/carp_v2_mirror`.
2. Python: root `runtime.txt` must be `3.11`.
3. Requirements: root `requirements.txt` must contain exactly:
   -r supabase/ui/requirements.txt
4. App entry point: `supabase/ui/streamlit_app.py`.
5. Secrets (in Streamlit → App settings → Secrets). Use `.streamlit/secrets.sample.toml` as a template and fill:
   DB_URL="postgresql://postgres:postgres@YOUR-PUBLIC-DB-HOST:5432/postgres?sslmode=require"
   SUPABASE_URL="https://YOUR-REF.supabase.co"
   SUPABASE_ANON_KEY="YOUR-ANON-KEY"
   APP_ENV="prod"
   APP_LOCKED=true
   APP_PASSWORD_SHA256="YOUR-SHA256-PASSWORD-HASH"

6. Generate password hash locally:
     python3 - <<'PY'
     import hashlib, getpass
     pw = getpass.getpass("Enter app password: ")
     print(hashlib.sha256(pw.encode()).hexdigest())
     PY
