BEGIN;

-- ensure tag_pos exists (noop if already there)
ALTER TABLE public.fusions ADD COLUMN IF NOT EXISTS tag_pos text;

-- old unique blocked multi-orientation; drop it if present
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM pg_indexes
    WHERE schemaname='public' AND indexname='uq_fusions_fluor_tag_notnull'
  ) THEN
    EXECUTE 'DROP INDEX public.uq_fusions_fluor_tag_notnull';
  END IF;
END$$;

-- fluor-only uniqueness when tag is NULL
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
END$$;

-- correct uniqueness when tag present: include tag_pos
DO $$
BEGIN
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
