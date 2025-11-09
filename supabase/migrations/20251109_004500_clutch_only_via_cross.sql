BEGIN;

-- Make cross required
ALTER TABLE public.clutch_instances
  ALTER COLUMN cross_id SET NOT NULL;

-- Drop any direct clutch→tank_pair pointers (code or id) + their FKs if present
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.columns
             WHERE table_schema='public' AND table_name='clutch_instances' AND column_name='tank_pair_id') THEN
    -- drop FK if it exists
    IF EXISTS (SELECT 1 FROM pg_constraint
               WHERE conrelid='public.clutch_instances'::regclass
                 AND conname='fk_clutch_instances_tank_pair_id') THEN
      ALTER TABLE public.clutch_instances DROP CONSTRAINT fk_clutch_instances_tank_pair_id;
    END IF;
    ALTER TABLE public.clutch_instances DROP COLUMN tank_pair_id;
  END IF;

  IF EXISTS (SELECT 1 FROM information_schema.columns
             WHERE table_schema='public' AND table_name='clutch_instances' AND column_name='tank_pair_code') THEN
    IF EXISTS (SELECT 1 FROM pg_constraint
               WHERE conrelid='public.clutch_instances'::regclass
                 AND conname='fk_clutch_instances_tank_pair_code') THEN
      ALTER TABLE public.clutch_instances DROP CONSTRAINT fk_clutch_instances_tank_pair_code;
    END IF;
    ALTER TABLE public.clutch_instances DROP COLUMN tank_pair_code;
  END IF;
END$$;

COMMIT;
