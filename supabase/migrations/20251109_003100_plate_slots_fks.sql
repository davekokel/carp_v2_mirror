BEGIN;

-- Support indexes
CREATE INDEX IF NOT EXISTS idx_plate_slots_plate_id         ON public.plate_slots(plate_id);
CREATE INDEX IF NOT EXISTS idx_plate_slots_treated_clutch_id ON public.plate_slots(treated_clutch_id);

-- plate_slots.plate_id → plates(id)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname='fk_plate_slots_plate_id__plates_id'
      AND conrelid='public.plate_slots'::regclass
  ) THEN
    ALTER TABLE public.plate_slots
      ADD CONSTRAINT fk_plate_slots_plate_id__plates_id
      FOREIGN KEY (plate_id) REFERENCES public.plates(id)
      DEFERRABLE INITIALLY DEFERRED
      NOT VALID;
  END IF;
END$$;

-- plate_slots.treated_clutch_id → treated_clutches(id) (only if table exists)
DO $$
BEGIN
  IF to_regclass('public.treated_clutches') IS NOT NULL
     AND NOT EXISTS (
       SELECT 1 FROM pg_constraint
       WHERE conname='fk_plate_slots_treated_clutch_id__treated_clutches_id'
         AND conrelid='public.plate_slots'::regclass
     ) THEN
    ALTER TABLE public.plate_slots
      ADD CONSTRAINT fk_plate_slots_treated_clutch_id__treated_clutches_id
      FOREIGN KEY (treated_clutch_id) REFERENCES public.treated_clutches(id)
      DEFERRABLE INITIALLY DEFERRED
      NOT VALID;
  END IF;
END$$;

COMMIT;
