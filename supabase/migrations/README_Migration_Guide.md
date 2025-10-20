Migration Guide — Freeze & Continue (Post-2025-10-15)

🧊 Concept: “Freeze & Continue”

On October 15, 2025, the CARP database schema was frozen. Everything before that date lives in the _archive_legacy/ folder and is no longer replayed. This gives us a clean, reproducible starting point for all future schema evolution.

From now on:
	•	Rebuild your local or staging database once using the full schema in bootstrap/bootstrap_public.sql (or a current /snapshots dump).
	•	Apply new, incremental migrations only from this folder (the post-freeze folder).

You no longer need to chain hundreds of legacy migration diffs — the baseline already captures them.

⸻

🪄 Workflow for New Migrations

Whenever you make a schema change (new table, view, trigger, etc.):
	1.	Edit your local database
Make your changes interactively via SQL or a tool like DBeaver, psql, or the Supabase Studio SQL editor.
	2.	Generate a migration file

supabase db diff -f <short_descriptive_name>

Example:

supabase db diff -f add_treatment_logs

This creates a new migration SQL file in the current folder containing only the diff between your local DB and the remote target.

	3.	Apply the migration

supabase db push

This applies your migration to staging (and, through CI, can propagate to production after review).

	4.	Commit the migration file

git add supabase/migrations/<timestamp>_<name>.sql
git commit -m "Add migration: <name>"
git push origin <branch>


	5.	Avoid clutter
Don’t commit scratch or duplicate files (like *.new, * 2.sql, or editor backups). Keep this folder clean and linear.

⸻

🔄 Rebuilding or Resetting a Database

If you need to recreate a database:
	1.	Restore from the latest snapshot in /snapshots or bootstrap/bootstrap_public.sql.
	2.	Then reapply all migrations in this folder (in order).

This ensures every environment (local, staging, production) starts from the same baseline and applies only verified post-freeze migrations.

⸻

⚙️ CI/CD Notes
	•	GitHub Actions automatically runs DB Push (Freeze & Continue) for new migrations merged into the main branch.
	•	Do not reset from migrations — use the full schema snapshot if you need to rebuild from scratch.
	•	CI validation ensures the schema in staging matches the expected state after each migration.

⸻

🧭 Summary
	•	Archive: _archive_legacy/ — old pre-freeze migrations.
	•	Baseline: bootstrap/bootstrap_public.sql or /snapshots/*.
	•	Current migrations: this folder.
	•	Commands: supabase db diff -f <name> → supabase db push.

Philosophy: Clean baseline once, small incremental diffs forever.