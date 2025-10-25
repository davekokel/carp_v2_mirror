# Migrations — Freeze & Continue (2025-10-15)

- Historical migrations have been archived; we do not replay them.
- Rebuild a fresh DB using `bootstrap/bootstrap_public.sql` once, then apply post-freeze migrations in this folder.
- CI uses GitHub Actions "DB Push (Freeze & Continue)" to apply new migrations to staging.
- Avoid committing duplicate/scratch files (`* 2.sql`, `*.new`, editor backups).
