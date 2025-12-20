BEGIN;

ALTER TABLE public.clutches
  ADD COLUMN IF NOT EXISTS genetic_background text;

CREATE INDEX IF NOT EXISTS idx_clutches_genetic_background
  ON public.clutches (genetic_background);

COMMIT;
