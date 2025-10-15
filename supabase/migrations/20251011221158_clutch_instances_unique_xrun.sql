-- Detect duplicates first (won't block migration, just prints rows);
DO $$
BEGIN
  RAISE NOTICE 'Duplicates (cross_instance_id, count):';
  -- This SELECT executes but does not return to client in DO; keep for reference
  -- SELECT cross_instance_id, count(*) FROM public.clutch_instances
  -- WHERE cross_instance_id IS NOT NULL GROUP BY 1 HAVING count(*)>1;
END
$$ LANGUAGE plpgsql;

-- Add a true UNIQUE CONSTRAINT (ON CONFLICT requires a constraint or a non-partial unique index);
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname='uq_ci_cross_instance_id'
      AND conrelid='public.clutch_instances'::regclass
  ) THEN
    ALTER TABLE public.clutch_instances
      ADD CONSTRAINT uq_ci_cross_instance_id UNIQUE (cross_instance_id);
  END IF;
END
$$ LANGUAGE plpgsql;
