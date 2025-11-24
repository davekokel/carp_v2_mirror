BEGIN;

-- Drop the global unique constraint on slot_label (the one that just bit us)
ALTER TABLE public.imaging_slots
  DROP CONSTRAINT IF EXISTS imaging_slots_slot_label_key;

-- Make sure we have a unique constraint at the right level:
-- one slot_index per plate_id.
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM   pg_indexes
    WHERE  schemaname = 'public'
    AND    indexname = 'imaging_slots_plate_slot_unique'
  ) THEN
    CREATE UNIQUE INDEX imaging_slots_plate_slot_unique
      ON public.imaging_slots(plate_id, slot_index);
  END IF;
END $$;

-- Optional: non-unique index on slot_label just for lookup speed
CREATE INDEX IF NOT EXISTS imaging_slots_slot_label_idx
  ON public.imaging_slots(slot_label);

COMMIT;
