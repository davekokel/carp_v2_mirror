# Inspection Guide

### If you just want to inspect **STAGING** (no risks)
You can connect with `psql` through the pooler in a read-only session. That way you’re looking at the real schema and data, but it’s impossible to damage anything.

**Connect:**
```bash
PGSSLMODE=require psql   -h aws-1-us-west-1.pooler.supabase.com -p 6543   -U postgres.<project-ref> -d postgres
```
It will prompt for the same password you already use for the pooler account.

**Make the session read-only:**
```sql
SET default_transaction_read_only = on;
SHOW default_transaction_read_only;  -- should return 'on'
```

**Useful queries (safe):**
```sql
-- Which migrations are applied
select version, name, cardinality(statements) as stmts
from supabase_migrations.schema_migrations
order by version;

-- Biggest tables
select relname as table, n_live_tup as approx_rows
from pg_stat_user_tables
order by n_live_tup desc
limit 20;

-- Example: table structure
select column_name, data_type
from information_schema.columns
where table_schema='public' and table_name='fish_plasmids'
order by ordinal_position;
```

---

### If you want a **playground** to try migrations or poke structure
Use the devcontainer. It gives you a safe local Postgres + tools setup so you can run migrations, seeds, and even break things without touching staging.

**Quick start:**
```bash
git clone https://github.com/cell-observatory/carp_v2.git
cd carp_v2
# Open in VS Code → “Reopen in Container” (uses .devcontainer/)
# Then inside the container terminal:
bash scripts/migrate.sh
```

Notes:
- Devcontainer is the right place to *draft/test* migrations. Once a migration looks good locally, commit it and open a PR; only after merge should it be applied to STAGING by the deployer.
- For *just looking* at STAGING, the read-only pooler session above is simpler.
