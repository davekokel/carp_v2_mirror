BEGIN;

ALTER TABLE public.plasmids
  ADD COLUMN IF NOT EXISTS resistance text;

COMMIT;
