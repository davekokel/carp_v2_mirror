DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conrelid = 'public.clutch_instances'::regclass
      AND conname  = 'uq_clutch_per_cross'
  ) THEN
    EXECUTE 'ALTER TABLE public.clutch_instances
             ADD CONSTRAINT uq_clutch_per_cross
             UNIQUE (cross_instance_id)';
  END IF;
END
$$;
