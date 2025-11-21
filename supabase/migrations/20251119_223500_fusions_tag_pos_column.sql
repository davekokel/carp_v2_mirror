BEGIN;

ALTER TABLE public.fusions
  ADD COLUMN IF NOT EXISTS tag_pos text;

COMMIT;
