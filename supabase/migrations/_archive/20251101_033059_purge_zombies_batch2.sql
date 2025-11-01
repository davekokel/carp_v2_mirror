DO $$
DECLARE
  t text;
  zombies text[] := ARRAY[
    -- legacy counters/logs/audit
    '_schema_version','allele_nicknames','fish_code_audit','fish_seed_batches','fish_seed_batches_map',
    'selection_labels','tank_pair_counters','tank_year_counters','tp_run_counters','transgene_allele_counters',
    'plasmid_registry','load_log_fish',
    -- legacy plans/treatments/containers
    'planned_crosses','clutch_plans','clutch_plan_treatments','clutch_treatments','clutch_containers',
    'container_status_history','clutch_genotype_options',
    -- injected materials (old)
    'injected_plasmid_treatments','injected_rna_treatments',
    -- misc
    'tank_requests','bruker_mounts'
  ];
BEGIN
  EXECUTE 'CREATE SCHEMA IF NOT EXISTS trash_carp';
  FOREACH t IN ARRAY zombies LOOP
    IF to_regclass(format('public.%I', t)) IS NOT NULL
       AND to_regclass(format('trash_carp.%I', t)) IS NULL THEN
      BEGIN
        EXECUTE format('ALTER TABLE public.%I SET SCHEMA trash_carp', t);
      EXCEPTION WHEN duplicate_table THEN
        -- already moved by prior step; ignore
        CONTINUE;
      END;
    END IF;
  END LOOP;
END$$;
