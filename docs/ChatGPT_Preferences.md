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

---

## 8. Verify-first checklist
Before starting any build, patch, or debug session:

1. **Verify the file tree**
   - Canonical pages directory: `carp_app/ui/pages`.
   - Do **not** create or use `supabase/ui/pages`; if present, it is a leftover symlink and can be removed.
   - Confirm where `streamlit_app.py` lives (`supabase/ui/streamlit_app.py`).
   - Confirm that all page files are under `carp_app/ui/pages/`.
   - Never assume a `supabase/ui/pages/` folder exists unless explicitly created.

2. **Confirm the active branch**
   - Run `git branch --show-current` and ensure it matches the intended feature branch.
   - Use `git status -sb` to confirm a clean working tree before applying any edits.

3. **Check the DB schema**
   - Validate that migrations are up to date and the correct database (local/staging/prod) is in use.
   - Use `make baseline-local` or `make baseline-staging` if schema drift is suspected.

4. **General principle**
   - Do not assume paths, branches, or schema versions.
   - Always inspect first, then apply targeted changes.

---

## 9. `.pgpass` hygiene (do not churn this file)
- Keep **one line per env** only:
  - Staging: `aws-1-us-west-1.pooler.supabase.com:6543:postgres:postgres.zebzrvjbalhazztvhhcm:<staging_pw>`
  - Prod:    `aws-1-us-east-2.pooler.supabase.com:6543:postgres:postgres.gzmbxhkckkspnefpxkgb:<prod_pw>`
- **No placeholders** in this file. If you see `<YOUR_...>`, replace it or delete the line.
- **Permissions** must be `0600`: `chmod 600 ~/.pgpass`.
- **Never auto-edit** `.pgpass` in scripts. Set/verify `DB_URL` instead (pooler DSN).
- Prefer `DB_URL` for apps; let libpq read `.pgpass` only for local psql usage.
- If authentication fails, check this file first—host, port, db, user, password must match exactly.

---

## 10. How to prime ChatGPT for new sessions

When starting a new conversation:

1. **Upload these two documents together**
   - `docs/ChatGPT_Preferences.md`
   - `docs/DB_Connection_Playbook.md`

2. **Say:**  
   > “Prime with these two docs. This is the canonical setup for CARP.”

3. **Purpose**
   - *ChatGPT_Preferences* → establishes formatting, workflow, and style conventions.  
   - *DB_Connection_Playbook* → defines connection policy, environment layout, and pgpass hygiene.

4. **Optional contextual docs**
   - Add specific pages (e.g., seed kit instructions, schema snapshots) only if we’re working in that area.

This pairing fully restores CARP context — no additional prompting required.
### 8.1 Full filetree check
Run this at the start of a session to verify the layout and entry files.

`bash`
cd ~/Documents/github/carp_v2
printf "\n== top ==\n"; ls -la
printf "\n== app/streamlit candidates ==\n"; rg -n --glob='**/*{app,main,streamlit_app}.py' -S | true
printf "\n== ui roots ==\n"; ls -la carp_app/ui 2>/devnull | true; ls -la supabase/ui 2>/devnull | true
printf "\n== pages roots ==\n"; ls -la carp_app/ui/pages 2>/devnull | true; ls -la supabase/ui/pages 2>/devnull | true
``ash`
## 11. Editing docs safely (default)

Use **Base64 append** to add Markdown blocks without quoting issues.

Steps:
1) Prepare your new section as Base64 and assign to B64.
2) Append it to the target file with this portable one-liner (macOS/Linux):
    cd ~/Documents/github/carp_v2
    if base64 --help 2>&1 | grep -q -- "invalid option --"; then
        printf "%s" "$B64" | base64 -D >> <target-file>
    else
        printf "%s" "$B64" | base64 -d >> <target-file>
    fi
3) Commit:
    git add <target-file> && git commit -m "docs: append section (base64)" && git push

Notes:
- Keep code blocks inside the appended content exactly as you want them rendered.
- This avoids heredoc/backtick mangling in chat and terminals.

### 8.2 File-tree verification
Before beginning any development or debugging session:

- Confirm the **canonical entry file** is `carp_app/ui/streamlit_app.py`.
- Confirm all Streamlit pages live under `carp_app/ui/pages/`.
- The `supabase/` folder is for backend/config only — it should **not** contain UI code.
- There should be **no** `supabase/ui` directory or symlink; remove if it appears.
- Run the full filetree check (section 8.1) whenever you suspect layout drift.
- Always verify actual tree output before writing migrations, modifying paths, or editing run scripts.
