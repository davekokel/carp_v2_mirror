# Freeze & Continue (2025-10-15)

We archived historical migrations under `_archive_legacy/`.
From now on, write migrations only for changes after today.

CI notes:
- Do not reset from migrations.
- Use: supabase db diff -f <name>  and  supabase db push.
- Full schema lives in /snapshots or the archive.
