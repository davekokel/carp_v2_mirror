BEGIN;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                 WHERE n.nspname='public' AND c.relname='fluors' AND c.relkind IN ('r','p')) THEN
    RAISE EXCEPTION 'missing table public.fluors; run baseline migrations first';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                 WHERE n.nspname='public' AND c.relname='tags' AND c.relkind IN ('r','p')) THEN
    RAISE EXCEPTION 'missing table public.tags; run baseline migrations first';
  END IF;
END$$;

CREATE TABLE IF NOT EXISTS public.fusions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  fluor_id uuid NOT NULL REFERENCES public.fluors(id),
  tag_id uuid NULL REFERENCES public.tags(id),
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE public.fusions
  ALTER COLUMN tag_id DROP NOT NULL;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_indexes WHERE schemaname='public' AND indexname='uq_fusions_fluor_tag_notnull'
  ) THEN
    CREATE UNIQUE INDEX uq_fusions_fluor_tag_notnull
      ON public.fusions(fluor_id, tag_id)
      WHERE tag_id IS NOT NULL;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_indexes WHERE schemaname='public' AND indexname='uq_fusions_fluor_when_tag_null'
  ) THEN
    CREATE UNIQUE INDEX uq_fusions_fluor_when_tag_null
      ON public.fusions(fluor_id)
      WHERE tag_id IS NULL;
  END IF;
END$$;

COMMIT;
