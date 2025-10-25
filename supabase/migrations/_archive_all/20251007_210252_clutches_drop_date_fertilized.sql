BEGIN;

-- Ensure date_birth exists
ALTER TABLE public.clutches
ADD COLUMN IF NOT EXISTS date_birth date;

-- Backfill date_birth from date_fertilized if needed
UPDATE public.clutches
SET date_birth = COALESCE(date_birth, date_fertilized)
WHERE TRUE;

-- Drop the old column
ALTER TABLE public.clutches
DROP COLUMN IF EXISTS date_fertilized;

COMMIT;
