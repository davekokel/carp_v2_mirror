BEGIN;

ALTER TABLE public.tank_pairs
  DROP COLUMN IF EXISTS active_from,
  DROP COLUMN IF EXISTS active_until;

COMMIT;
