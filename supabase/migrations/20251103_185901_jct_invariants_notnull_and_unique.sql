BEGIN;

-- Only set NOT NULL if there are no nulls
DO $$
DECLARE n int;
BEGIN
  SELECT count(*) INTO n
  FROM public.join_clutch_treatments
  WHERE treatment_id IS NULL;
  IF n = 0 THEN
    BEGIN
      ALTER TABLE public.join_clutch_treatments
        ALTER COLUMN treatment_id SET NOT NULL;
    EXCEPTION WHEN others THEN
      RAISE NOTICE 'Skipped NOT NULL on join_clutch_treatments.treatment_id';
    END;
  ELSE
    RAISE NOTICE 'Skipped NOT NULL on join_clutch_treatments.treatment_id (% null rows)', n;
  END IF;
END$$;

-- Unique per clutch+treatment
DO $$
BEGIN
  CREATE UNIQUE INDEX IF NOT EXISTS uq_jct_clutch_treatment
    ON public.join_clutch_treatments (clutch_instance_id, treatment_id);
EXCEPTION WHEN duplicate_table OR unique_violation THEN
  RAISE NOTICE 'uq_jct_clutch_treatment already enforced or duplicates exist';
END$$;

COMMIT;
