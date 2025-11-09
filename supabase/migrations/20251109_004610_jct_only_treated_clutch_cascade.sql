BEGIN;

-- Drop the clutch_instance pointer from join_clutch_treatments,
-- removing any dependent views along the way.
DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema='public'
      AND table_name='join_clutch_treatments'
      AND column_name='clutch_instance_id'
  ) THEN
    -- Drop FK first if present (name-guarded)
    IF EXISTS (
      SELECT 1 FROM pg_constraint
      WHERE conrelid='public.join_clutch_treatments'::regclass
        AND conname='fk_join_clutch_treatments_clutch_instance_id'
    ) THEN
      ALTER TABLE public.join_clutch_treatments
        DROP CONSTRAINT fk_join_clutch_treatments_clutch_instance_id;
    END IF;

    -- Now drop the column and any dependent views
    ALTER TABLE public.join_clutch_treatments
      DROP COLUMN clutch_instance_id CASCADE;
  END IF;
END$$;

-- Ensure the intended parent link (treated_clutch_id) is indexed + FK'd
CREATE INDEX IF NOT EXISTS idx_jct_treated_clutch_id
  ON public.join_clutch_treatments(treated_clutch_id);

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid='public.join_clutch_treatments'::regclass
      AND conname='fk_jct_treated_clutch_id__treated_clutches_id'
  ) THEN
    ALTER TABLE public.join_clutch_treatments
      ADD CONSTRAINT fk_jct_treated_clutch_id__treated_clutches_id
      FOREIGN KEY (treated_clutch_id) REFERENCES public.treated_clutches(id)
      DEFERRABLE INITIALLY DEFERRED NOT VALID;
  END IF;
END$$;

COMMIT;
