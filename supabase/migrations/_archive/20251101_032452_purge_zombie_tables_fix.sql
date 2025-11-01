DO $do$
DECLARE
  rec record;
BEGIN
  EXECUTE 'CREATE SCHEMA IF NOT EXISTS trash_carp';

  FOR rec IN
    SELECT c.relname
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE c.relkind IN ('r','p')
      AND n.nspname = 'public'
      AND c.relname <> ALL(ARRAY[
        'fish','tanks','tank_pairs',
        'fish_tank_memberships','fish_transgene_alleles',
        'transgenes','transgene_alleles','transgene_allele_registry',
        'fish_year_counters','containers','tank_status_history',
        'cross_instances','crosses','clutches','clutch_instances',
        'plasmids','fluors','tags','fusions','plasmid_fusions',
        'label_jobs','label_items','mounts','clutch_materials'
      ])
      AND to_regclass(format('trash_carp.%I', c.relname)) IS NULL
  LOOP
    BEGIN
      EXECUTE format('ALTER TABLE public.%I SET SCHEMA trash_carp', rec.relname);
    EXCEPTION
      WHEN duplicate_table THEN CONTINUE;
      WHEN undefined_table THEN CONTINUE;
    END;
  END LOOP;
END
$do$;
