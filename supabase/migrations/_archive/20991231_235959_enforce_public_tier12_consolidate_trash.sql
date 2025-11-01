DO $$
DECLARE
  trash text := 'trash_carp';
  keep  text[] := ARRAY[
    -- Tier 1
    'fish','tanks','fish_tank_memberships','fish_transgene_alleles',
    'transgene_alleles','transgenes','fish_year_counters',
    -- Tier 2
    'cross_plans','cross_plan_runs','cross_plan_treatments','cross_plan_genotype_alleles',
    'cross_instances','clutches','clutch_instances',
    'tank_pairs','tank_status_history',
    'containers','label_jobs','label_items',
    'transgene_allele_registry','mounts','plasmids'
  ];
  r record;
BEGIN
  EXECUTE format('create schema if not exists %I', trash);

  FOR r IN
    SELECT c.relname AS tbl
    FROM pg_class c
    JOIN pg_namespace n ON n.oid=c.relnamespace
    WHERE c.relkind IN ('r','p') AND n.nspname='public'
      AND c.relname <> ALL(keep)
  LOOP
    -- If a prior trash copy exists, drop it so we can move the fresh one
    IF to_regclass(format('%I.%I', trash, r.tbl)) IS NOT NULL THEN
      EXECUTE format('DROP TABLE %I.%I CASCADE', trash, r.tbl);
    END IF;
    -- Move public → trash
    IF to_regclass(format('%I.%I','public',r.tbl)) IS NOT NULL THEN
      EXECUTE format('ALTER TABLE %I.%I SET SCHEMA %I', 'public', r.tbl, trash);
    END IF;
  END LOOP;
END $$;
