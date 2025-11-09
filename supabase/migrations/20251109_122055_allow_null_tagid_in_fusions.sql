BEGIN;

ALTER TABLE public.fusions
  ALTER COLUMN tag_id DROP NOT NULL;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_indexes
    WHERE schemaname='public' AND indexname='uq_fusions_fluor_tag_notnull'
  ) THEN
    CREATE UNIQUE INDEX uq_fusions_fluor_tag_notnull
      ON public.fusions(fluor_id, tag_id)
      WHERE tag_id IS NOT NULL;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_indexes
    WHERE schemaname='public' AND indexname='uq_fusions_fluor_when_tag_null'
  ) THEN
    CREATE UNIQUE INDEX uq_fusions_fluor_when_tag_null
      ON public.fusions(fluor_id)
      WHERE tag_id IS NULL;
  END IF;
END$$;

COMMIT;
