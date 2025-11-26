BEGIN;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_indexes
    WHERE schemaname = 'public'
      AND tablename = 'fusions'
      AND indexname = 'uniq_fusions_fluor_tag_pos'
  ) THEN
    CREATE UNIQUE INDEX uniq_fusions_fluor_tag_pos
      ON public.fusions (fluor_id, tag_id, tag_pos);
  END IF;
END;
$$;

COMMIT;
