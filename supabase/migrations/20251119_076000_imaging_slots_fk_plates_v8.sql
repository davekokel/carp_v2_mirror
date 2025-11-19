BEGIN;

----------------------------------------------------------------------
-- v8: ensure imaging_slots.plate_id properly references imaging_plates(id)
-- This is the canonical link that ties plates into the imaging graph:
--   imaging_plates.id ← imaging_slots.plate_id
----------------------------------------------------------------------

-- Drop any old/partial plate FKs if they exist
ALTER TABLE public.imaging_slots
  DROP CONSTRAINT IF EXISTS imaging_slots_plate_id_fkey,
  DROP CONSTRAINT IF EXISTS fk_imaging_slots_plate,
  DROP CONSTRAINT IF EXISTS fk_imaging_slots_imaging_plates;

-- Add the canonical FK
ALTER TABLE public.imaging_slots
  ADD CONSTRAINT fk_imaging_slots_plate
  FOREIGN KEY (plate_id)
  REFERENCES public.imaging_plates(id)
  ON UPDATE CASCADE ON DELETE RESTRICT;

COMMIT;
