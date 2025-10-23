BEGIN;

-- Make clutch_code unique (idempotent)
ALTER TABLE public.clutches
  ADD CONSTRAINT clutches_code_unique UNIQUE (clutch_code);

-- Helpful index (if not already present)
CREATE INDEX IF NOT EXISTS idx_clutches_code ON public.clutches(clutch_code);

COMMIT;
