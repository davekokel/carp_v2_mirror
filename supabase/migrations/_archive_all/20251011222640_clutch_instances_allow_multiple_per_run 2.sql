DO $$
BEGIN
  -- Drop named unique constraint if present
  IF EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname='uq_ci_cross_instance_id'
      AND conrelid='public.clutch_instances'::regclass
  ) THEN
    ALTER TABLE public.clutch_instances
      DROP CONSTRAINT uq_ci_cross_instance_id;
  END IF;

  -- Drop any unique index variant we may have added earlier (safety)
  IF EXISTS (
    SELECT 1
    FROM pg_indexes
    WHERE schemaname='public'
      AND indexname='ux_ci_cross_instance_id'
  ) THEN
    DROP INDEX public.ux_ci_cross_instance_id;
  END IF;

  -- Optional: ensure a plain (non-unique) index for performance
  IF NOT EXISTS (
    SELECT 1
    FROM pg_indexes
    WHERE schemaname='public'
      AND indexname='ix_ci_cross_instance_id'
  ) THEN
    CREATE INDEX ix_ci_cross_instance_id
      ON public.clutch_instances(cross_instance_id);
  END IF;
END
$$ LANGUAGE plpgsql;
