BEGIN;
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='plate_slots' AND column_name='fish_code'
  ) THEN
    IF EXISTS (
      SELECT 1 FROM pg_constraint
      WHERE conrelid='public.plate_slots'::regclass
        AND conname='fk_plate_slots_fish_code'
    ) THEN
      ALTER TABLE public.plate_slots DROP CONSTRAINT fk_plate_slots_fish_code;
    END IF;
    ALTER TABLE public.plate_slots DROP COLUMN fish_code;
  END IF;
END$$;
COMMIT;
