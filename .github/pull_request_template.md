## Checklist

- [ ] Migrations follow `YYYYMMDD_HHMMSS_slug.sql` (use `scripts/new_migration.sh`)
- [ ] Local: `make verify-id-only` passes or `psql -f scripts/verify_id_only.sql` passes
- [ ] No view rewrites re-introduce `id_uuid` in definitions or outputs
- [ ] If touching auth or pages, app still boots locally

## Notes

- The CI job `DB Verify (id-only)` will rebuild a clean Postgres, apply **all** migrations, and run `scripts/verify_id_only.sql`.
