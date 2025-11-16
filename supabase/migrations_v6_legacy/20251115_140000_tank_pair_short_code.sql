BEGIN;

ALTER TABLE public.tank_pairs
ADD COLUMN IF NOT EXISTS tank_pair_short_code text;

-- Backfill new short codes if missing
UPDATE public.tank_pairs
SET tank_pair_short_code = 'TP-' || LEFT(id::text, 8)
WHERE tank_pair_short_code IS NULL;

-- Ensure uniqueness
CREATE UNIQUE INDEX IF NOT EXISTS uq_tank_pair_short_code
ON public.tank_pairs (tank_pair_short_code);

COMMIT;
