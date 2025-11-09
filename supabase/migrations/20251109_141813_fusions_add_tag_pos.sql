BEGIN;
ALTER TABLE public.fusions ADD COLUMN IF NOT EXISTS tag_pos text;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname='ck_fusions_tag_pos' AND conrelid='public.fusions'::regclass
  ) THEN
    ALTER TABLE public.fusions
      ADD CONSTRAINT ck_fusions_tag_pos CHECK (tag_pos IS NULL OR tag_pos IN ('N','C'));
  END IF;
END$$;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_indexes
    WHERE schemaname='public' AND indexname='uq_fusions_fluor_when_tag_null'
  ) THEN
    CREATE UNIQUE INDEX uq_fusions_fluor_when_tag_null
      ON public.fusions(fluor_id)
      WHERE tag_id IS NULL;
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_indexes
    WHERE schemaname='public' AND indexname='uq_fusions_fluor_tag_pos_notnull'
  ) THEN
    CREATE UNIQUE INDEX uq_fusions_fluor_tag_pos_notnull
      ON public.fusions(fluor_id, tag_id, tag_pos)
      WHERE tag_id IS NOT NULL;
  END IF;
END$$;
COMMIT;
