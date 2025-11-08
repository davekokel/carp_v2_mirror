BEGIN;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_indexes
    WHERE schemaname='public'
      AND tablename='plate_slots'
      AND indexname='uq_plate_slots_loc'
  ) THEN
    CREATE UNIQUE INDEX uq_plate_slots_loc
      ON public.plate_slots(plate_id, row_idx, col_idx);
  END IF;
END $$;

COMMIT;
