DO $$
DECLARE
  tgt_schema text := 'trash_carp';
  t text;
BEGIN
  -- Ensure quarantine exists
  EXECUTE format('CREATE SCHEMA IF NOT EXISTS %I', tgt_schema);

  -- Only these four: move to trash if they exist in public
  FOREACH t IN ARRAY ARRAY[
    'cross_plan_genotype_alleles',
    'cross_plan_treatments',
    'cross_plan_runs',
    'cross_plans'
  ]
  LOOP
    IF to_regclass(format('public.%I', t)) IS NOT NULL THEN
      -- Move table; ignore if a homonym already in trash
      BEGIN
        EXECUTE format('ALTER TABLE public.%I SET SCHEMA %I', t, tgt_schema);
      EXCEPTION WHEN duplicate_table THEN
        -- If a table already exists in trash, just drop the public one instead of failing
        EXECUTE format('DROP TABLE public.%I CASCADE', t);
      END;
    END IF;
  END LOOP;
END $$;
