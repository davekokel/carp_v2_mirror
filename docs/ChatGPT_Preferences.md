# ChatGPT Preferences

## 1. Output style
- Shell code: always copy-pasteable, no comments or prompts.
- Prefer `zsh`-compatible commands.
- Multi-statement SQL → heredoc piped to `psql`.
- One-liners → `psql -Atc "..."`.
- Use underscores in filenames and numeric suffixes for versions.
- Avoid `sex` columns anywhere in the CARP schema.

## 2. Environment conventions
- Supabase project ref (staging): `zebzrvjbalhazztvhhcm`.
- Local DB: Homebrew Postgres on `127.0.0.1:5432`.
- Always use **pooler** hosts (`aws-<cluster>-<region>.pooler.supabase.com:6543`).
- Env switchers in `~/.zshrc`: `use_local`, `use_staging`, `use_prod` (set `DB_URL`).
- Passwords via `~/.pgpass` under `~/.secrets` (pooler usernames include the project ref).
- `scripts/run_staging.sh` launches Streamlit with the staging DSN and app entry.

## 3. Repo layout reminders
```
carp_app/ui/app.py                # Streamlit entry (shows sidebar)
carp_app/ui/pages/029_🧰_crosses_workbench.py
supabase/migrations/
supabase/seed_kits/
docs/DB_Connection_Playbook.md
```

## 4. Frequent shell helpers
```bash
use_local(){ export DB_URL="$LOCAL_DB_URL"; printf "DB_URL=%s
" "$DB_URL"; }
use_staging(){ export DB_URL="$STAGING_DB_URL"; printf "DB_URL=%s
" "$DB_URL"; }
use_prod(){ export DB_URL="$PROD_DB_URL"; printf "DB_URL=%s
" "$DB_URL"; }
```

## 5. Typical workflows
- Run app (staging): `bash scripts/run_staging.sh`
- Verify DB: `bash scripts/db_connect_doctor.sh`
- DB snapshots: `make snapshot-local` / `make snapshot-staging`
- Reset staging: `make baseline-staging`

## 6. Conversation bootstrap
Paste this doc into ChatGPT at the start of each session so preferences, env layout, and shortcuts are “loaded.”

## 7. Living document
Treat this file as a living, iterative guide.
- Continually add new preferences, examples, and workflows as they evolve.
- Update older sections whenever conventions or repo structure change.
- Keep expanding it so a single drop into a new ChatGPT chat fully restores context and style.

### 5.1 Streamlit Cloud / Production
- Use **secrets**, not `~/.pgpass`:
  ```toml
  # .streamlit/secrets.toml
  DB_URL = "postgresql://postgres.gzmbxhkckkspnefpxkgb:<PROD_PASSWORD>@aws-0-us-east-2.pooler.supabase.com:6543/postgres?sslmode=require"
  ```
- App reads `DB_URL` directly; nothing else required.

### 5.2 Pooler auto-rewrite safety net
- The app will auto-rewrite `db.<ref>.supabase.co:5432` → pooler host/user for known refs.
- Toggle via env var:
  ```bash
  export POOLER_AUTOREWRITE=0  # disable rewrite if you intentionally test direct host
  ```
