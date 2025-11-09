BEGIN;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='clutch_instances' AND column_name='cross_instance_id'
  ) THEN
    IF NOT EXISTS (
      SELECT 1 FROM pg_constraint
      WHERE conrelid='public.clutch_instances'::regclass
        AND conname='fk_clutch_instances_cross_instance_id__crosses_id'
    ) THEN
      ALTER TABLE public.clutch_instances
        ADD CONSTRAINT fk_clutch_instances_cross_instance_id__crosses_id
        FOREIGN KEY (cross_instance_id) REFERENCES public.crosses(id)
        DEFERRABLE INITIALLY DEFERRED NOT VALID;
    END IF;
    ALTER TABLE public.clutch_instances
      ALTER COLUMN cross_instance_id SET NOT NULL;
  END IF;
END$$;

COMMIT;
