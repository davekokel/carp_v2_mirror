BEGIN;

DO $$
DECLARE has_concept boolean;
BEGIN
  SELECT EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema='public' AND table_name='tank_pairs' AND column_name='concept_id'
  ) INTO has_concept;

  IF has_concept THEN
    -- Unique among active/current pairs (concept_id is NULL)
    IF NOT EXISTS (
      SELECT 1 FROM pg_indexes
      WHERE schemaname='public' AND tablename='tank_pairs' AND indexname='uq_tank_pairs_parents_null_concept'
    ) THEN
      EXECUTE $ix$
        CREATE UNIQUE INDEX uq_tank_pairs_parents_null_concept
          ON public.tank_pairs(mother_tank_id, father_tank_id)
          WHERE concept_id IS NULL
      $ix$;
    END IF;
  ELSE
    -- No concept_id column; enforce uniqueness across all rows
    IF NOT EXISTS (
      SELECT 1 FROM pg_indexes
      WHERE schemaname='public' AND tablename='tank_pairs' AND indexname='uq_tank_pairs_parents'
    ) THEN
      EXECUTE $ix$
        CREATE UNIQUE INDEX uq_tank_pairs_parents
          ON public.tank_pairs(mother_tank_id, father_tank_id)
      $ix$;
    END IF;
  END IF;
END $$;

COMMIT;
