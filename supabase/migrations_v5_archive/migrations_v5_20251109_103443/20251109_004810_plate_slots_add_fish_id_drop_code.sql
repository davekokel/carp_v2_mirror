BEGIN;

-- 1) Add fish_id and its FK (structure-first; validate after clean seed)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='plate_slots' AND column_name='fish_id'
  ) THEN
    ALTER TABLE public.plate_slots ADD COLUMN fish_id uuid;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_indexes
    WHERE schemaname='public' AND tablename='plate_slots' AND indexname='idx_plate_slots_fish_id'
  ) THEN
    CREATE INDEX idx_plate_slots_fish_id ON public.plate_slots(fish_id);
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid='public.plate_slots'::regclass
      AND conname='fk_plate_slots_fish_id__fish_id'
  ) THEN
    ALTER TABLE public.plate_slots
      ADD CONSTRAINT fk_plate_slots_fish_id__fish_id
      FOREIGN KEY (fish_id) REFERENCES public.fish(id)
      DEFERRABLE INITIALLY DEFERRED NOT VALID;
  END IF;
END$$;

-- 2) Drop legacy fish_code (and any dependent views) cleanly
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='plate_slots' AND column_name='fish_code'
  ) THEN
    -- Drop code-FK if present
    IF EXISTS (
      SELECT 1 FROM pg_constraint
      WHERE conrelid='public.plate_slots'::regclass
        AND conname='fk_plate_slots_fish_code'
    ) THEN
      ALTER TABLE public.plate_slots DROP CONSTRAINT fk_plate_slots_fish_code;
    END IF;

    -- This will DROP any views (e.g., v_plate_layout) that still reference fish_code
    ALTER TABLE public.plate_slots DROP COLUMN fish_code CASCADE;
  END IF;
END$$;

COMMIT;
