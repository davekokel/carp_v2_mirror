---

## 🚀 Quickstart (Staging / Production)

### 🧪 Staging (direct 5432)
Runs the app against Supabase **staging** with full write access.

```bash
make run-staging
```

**Expected on launch**
- Yellow banner → **STAGING • Cloud**
- `PG env → host=db.zebzrvjbalhazztvhhcm.supabase.co port=5432`
- Row counts load under **Diagnostics (Clean)**

---

### 🔒 Production (read-only)
Runs the app in **read-only mode** on the production Supabase database using the `app_ro` role.

```bash
make run-prod-ro
```

**Expected on launch**
- Red banner → **PRODUCTION — READ-ONLY**
- `PG env → host=db.xdwzmqbrbkhmhcjwkopr.supabase.co port=5432`
- Row counts load normally
- “Danger zone” section shows **“disabled outside LOCAL”**

---

### 🧰 Local developmentß
Use your local Supabase or Homebrew Postgres.

```bash
supabase start
make run-local
```

(Local launcher optional if you add a `scripts/run_local_clean.sh` that sources `.env.local`.)

---

### 🩺 Health checks
Run a one-line connectivity test against staging or prod:

```bash
make health-staging
make health-prod-ro
```

Each prints something like:
```
OK: host=db.… port=5432 db=postgres user=app_ro → latency≈120 ms
```

---

### 🧱 Environment files
| File | Purpose |
|------|----------|
| `.env.staging.direct` | Direct connection to Supabase staging (read/write) |
| `.env.prod.ro` | Direct connection to Supabase production (read-only) |
| `.env.local` *(optional)* | Local Postgres for dev experiments |

All app launches are **clean-env** (no leaked variables).

---

### ⚠️ Safety rails
- **Danger zone disabled** outside local
- **Prod banner** always visible
- `app_ro` user has only `SELECT` privileges
- `make health-*` must pass before running migrations

---