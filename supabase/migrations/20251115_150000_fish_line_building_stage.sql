BEGIN;

-- 1) Ensure line_building_stage exists
ALTER TABLE public.fish
  ADD COLUMN IF NOT EXISTS line_building_stage text;

-- 2) If in_breeding_stage exists, backfill line_building_stage from it
DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name   = 'fish'
      AND column_name  = 'in_breeding_stage'
  ) THEN
    UPDATE public.fish
    SET line_building_stage = COALESCE(line_building_stage, in_breeding_stage);
  END IF;
END$$;

-- (Optional for now)
-- 3) Do NOT drop in_breeding_stage yet; we just stop using it in code.
-- ALTER TABLE public.fish DROP COLUMN IF EXISTS in_breeding_stage;

COMMIT;
