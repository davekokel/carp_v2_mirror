-- Purge “zombie” tables: move public non-core tables with no normal deps to trash_carp
-- Idempotent: safe to run multiple times

CREATE SCHEMA IF NOT EXISTS trash_carp;

DO $$
DECLARE
  rec record;
BEGIN
  -- Core keep-set: tables that must remain in public
  -- (Aligns with the state you confirmed as “last green”)
  WITH keep AS (
    SELECT unnest(ARRAY[
      'fish','tanks',
      'fish_tank_memberships','fish_transgene_alleles',
      'transgene_alleles','transgenes','fish_year_counters',
      'cross_instances',
      'clutches','clutch_instances',
      'tank_pairs','tank_status_history',
      'containers','label_jobs','label_items',
      'transgene_allele_registry','mounts',
      'plasmids','fluors','tags','fusions',
      'plasmid_fusions',
      'clutch_materials'
    ]) AS name
  ),
  pub AS (
    SELECT c.oid, c.relname
    FROM pg_class c
    JOIN pg_namespace n ON n.oid=c.relnamespace
    WHERE c.relkind IN ('r','p') AND n.nspname='public'
  ),
  noncore AS (
    -- public tables not in keep
    SELECT p.oid, p.relname
    FROM pub p
    LEFT JOIN keep k ON k.name = p.relname
    WHERE k.name IS NULL
  ),
  deps AS (
    -- count only "normal" dependencies (deptype='n'); ignore auto/extension/internal
    SELECT d.refobjid AS oid, COUNT(*) FILTER (WHERE d.deptype='n') AS n_normal
    FROM pg_depend d
    GROUP BY d.refobjid
  )
  FOR rec IN
    SELECT nc.relname
    FROM noncore nc
    LEFT JOIN deps d ON d.oid = nc.oid
    WHERE COALESCE(d.n_normal,0) = 0
  LOOP
    -- Move table if it's still in public and not already in trash
    IF to_regclass(format('public.%I', rec.relname)) IS NOT NULL
       AND to_regclass(format('trash_carp.%I', rec.relname)) IS NULL THEN
      EXECUTE format('ALTER TABLE public.%I SET SCHEMA trash_carp', rec.relname);
    END IF;
  END LOOP;
END $$;

-- Optional: quick inventory after move (helps verify effect in CI logs)
-- SELECT n.nspname AS schema, COUNT(*) AS tables
-- FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
-- WHERE c.relkind IN ('r','p') AND n.nspname IN ('public','trash_carp')
-- GROUP BY 1 ORDER BY 1;
