DO $$
DECLARE
  trash text := 'trash_carp';
  owner_oid oid := (SELECT oid FROM pg_roles WHERE rolname = current_user);
  rec record;
  keep text[] := ARRAY[
    'fish','tanks','fish_tank_memberships','fish_transgene_alleles',
    'transgene_alleles','transgenes','fish_year_counters',
    'cross_plans','cross_plan_runs','cross_plan_treatments','cross_plan_genotype_alleles',
    'cross_instances','clutches','clutch_instances',
    'tank_pairs','tank_status_history',
    'containers','label_jobs','label_items',
    'transgene_allele_registry',
    'mounts','plasmids'
  ];
BEGIN
  EXECUTE format('create schema if not exists %I', trash);
  FOR rec IN
    SELECT n.nspname AS schema_name, c.relname AS table_name
    FROM pg_class c
    JOIN pg_namespace n ON n.oid=c.relnamespace
    WHERE c.relkind IN ('r','p')
      AND n.nspname='public'
      AND c.relowner = owner_oid
      AND NOT (c.relname = ANY(keep))
  LOOP
    IF to_regclass(format('%I.%I',trash,rec.table_name)) IS NULL THEN
      EXECUTE format('ALTER TABLE %I.%I SET SCHEMA %I', rec.schema_name, rec.table_name, trash);
    END IF;
  END LOOP;
END $$;
