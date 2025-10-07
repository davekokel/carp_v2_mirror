BEGIN;

ALTER TABLE public.fish
  ADD COLUMN IF NOT EXISTS genetic_background text;


COMMIT;
