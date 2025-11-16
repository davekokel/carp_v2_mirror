BEGIN;

-- Drop the FK if present
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname='fk_tc_fish' AND conrelid='public.treated_clutches'::regclass) THEN
    ALTER TABLE public.treated_clutches DROP CONSTRAINT fk_tc_fish;
  END IF;
END$$;

-- Drop the column if it exists
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='treated_clutches' AND column_name='fish_id'
  ) THEN
    ALTER TABLE public.treated_clutches DROP COLUMN fish_id;
  END IF;
END$$;

COMMIT;
