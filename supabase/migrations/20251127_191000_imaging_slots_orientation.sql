BEGIN;

ALTER TABLE public.imaging_slots
  ADD COLUMN IF NOT EXISTS orientation text;

COMMIT;
