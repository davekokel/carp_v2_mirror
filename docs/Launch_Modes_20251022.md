
# Launch & Deploy Modes — CARP

| **Mode** | **Runs where** | **DB target** | **Purpose / Typical use** | **Command** |
|-----------|----------------|----------------|----------------------------|--------------|
| **Local → Local** | Your laptop | Local Supabase (port 54322) | Full local dev & migration testing | `use_local && streamlit run supabase/ui/streamlit_app.py` |
| **Local → Staging** | Your laptop | Supabase staging (pooler 6543) | Sanity-check staging data with local code | `use_staging && streamlit run supabase/ui/streamlit_app.py` |
| **Local → Prod** | Your laptop | Supabase prod (pooler 6543) | Quick spot-checks on prod data | `use_prod && streamlit run supabase/ui/streamlit_app.py` |
| **Local helper script** | Your laptop | Staging DB | Legacy shorthand for above | `scripts/run_staging.sh` |
| **Make targets** | Your laptop | Depends on target | Consistent launcher shortcuts | `make app-local` / `make app-staging` / `make app-prod` |
| **Streamlit Cloud (Staging)** | Streamlit Cloud | Supabase staging (pooler 6543) | Published staging app for team testing | `git push mirror HEAD:staging` |
| **Streamlit Cloud (Prod)** | Streamlit Cloud | Supabase prod (pooler 6543) | Live production deployment | `git push mirror HEAD:prod` |
| **Supabase local stack** | Docker (local) | Local Supabase | Bring up DB + auth + storage services | `supabase start` |
| **DB sanity check** | Any | Current $DB_URL | Verify connection & identity | `psql "$DB_URL" -Atc "select 'ok', inet_server_addr(), current_user"` |

---

_Last updated: 2025-10-22_
