BEGIN;
DO $$
BEGIN
  RAISE NOTICE 'Skipping parent-genotype via view: v_cross_clutch_instances not available at this step.';
END $$;
COMMIT;
