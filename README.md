
## Inspecting STAGING (read-only)

If you just need to look at the live schema/data safely:

```bash
PGSSLMODE=require psql   -h aws-1-us-west-1.pooler.supabase.com -p 6543   -U postgres.<project-ref> -d postgres
```

Then in `psql`:

```sql
SET default_transaction_read_only = on;
SHOW default_transaction_read_only;
```

See the full guide with copy‑paste queries in `docs/INSPECTION.md`.



### Staging DB (read-only) from Dev Container

Docker can’t reach Supabase’s IPv6-only direct host. Use the **connection pooler** (IPv4) and a **project-qualified** user.

**Example `.streamlit/secrets.toml`:**
```toml
DB_URL = "host=aws-1-<region>.pooler.supabase.com port=6543 dbname=postgres user=teammate_ro.<PROJECT_REF> password=<PW> sslmode=require channel_binding=disable"
SUPABASE_URL = "https://<PROJECT_REF>.supabase.co"
SUPABASE_ANON_KEY = "<ANON-KEY>"
APP_PASSWORD = "letmein"
READ_ONLY = "true"
```

## Deploy to Streamlit Cloud

1. Repo: use the mirror repo `davekokel/carp_v2_mirror`.
2. Python: root `runtime.txt` must be `3.11`.
3. Requirements: root `requirements.txt` must contain exactly:
   ```
   -r supabase/ui/requirements.txt
   ```
4. App entry point: `supabase/ui/streamlit_app.py`.
5. Secrets (in Streamlit → App settings → Secrets) are stored in `.streamlit/secrets.toml` 
   - Use contents of `.streamlit/secrets.sample.toml` as a template
   - Use contents of `.streamlit/secrets.localsupabase.toml` to connect to locally run Supabase.

6. Generate a hash for a different password via:
   ```shell
   python3 - <<'PY'
   import hashlib, getpass
   pw = getpass.getpass("Enter app password: ")
   print(hashlib.sha256(pw.encode()).hexdigest())
   PY
   ```
