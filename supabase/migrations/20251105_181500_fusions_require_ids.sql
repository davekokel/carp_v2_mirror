BEGIN;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='fusions' AND column_name='fluor_id'
  ) THEN
    ALTER TABLE public.fusions ADD COLUMN fluor_id uuid;
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='fusions' AND column_name='tag_id'
  ) THEN
    ALTER TABLE public.fusions ADD COLUMN tag_id uuid;
  END IF;
END$$;
ALTER TABLE public.fusions
  DROP CONSTRAINT IF EXISTS fusions_fluor_id_fkey,
  ADD  CONSTRAINT fusions_fluor_id_fkey FOREIGN KEY (fluor_id) REFERENCES public.fluors(id) ON DELETE RESTRICT;
ALTER TABLE public.fusions
  DROP CONSTRAINT IF EXISTS fusions_tag_id_fkey,
  ADD  CONSTRAINT fusions_tag_id_fkey  FOREIGN KEY (tag_id)   REFERENCES public.tags(id)   ON DELETE RESTRICT;
COMMIT;
