# Scripts

## Purpose
Runnable entrypoints for local dev, loading seed kits, and migration hygiene.

## Common commands
- `scripts/carp_local_start` — start local app with env set for Homebrew DB
- `scripts/migrate.sh` — apply migrations in `supabase/migrations/` to $DB_URL
- `scripts/apply_migrations.sh` — one-shot apply with explicit DB_URL
- `scripts/load_seedkit_core_local.sh` — load core seed kit into local DB
- `scripts/load_csvs.sh` — load raw CSVs
- `scripts/guard_migration.py` — sanity-check migration filenames/order

## Tips
- Set `DB_URL` before running DB-affecting scripts.
- Use `make guard-migrations` before committing new migrations.
