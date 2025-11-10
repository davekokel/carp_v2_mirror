BEGIN;

-- Safety: required extension for gen_random_uuid
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Optional: a sequence for future treated_clutch codes after #0
CREATE SEQUENCE IF NOT EXISTS public.treated_clutch_seq;

-- Backfill: create a single default treated clutch (#0) for any clutch with none
WITH missing AS (
  SELECT ci.id AS clutch_instance_id,
         ci.clutch_instance_code
  FROM public.clutch_instances ci
  LEFT JOIN public.treated_clutches tc
    ON tc.clutch_instance_id = ci.id
  WHERE tc.id IS NULL
)
INSERT INTO public.treated_clutches (id, treated_clutch_code, clutch_instance_id, created_at)
SELECT
  gen_random_uuid(),
  COALESCE(NULLIF(m.clutch_instance_code,''),'CI') || '#0',
  m.clutch_instance_id,
  now()
FROM missing m;

-- Enforce exactly one "default" per clutch_instance (#0).
-- If you anticipate multiple treated clutches later, keep this UNIQUE;
-- you'll still be able to add additional entries with codes != '#0' by
-- relaxing the logic below to be a partial index. For now: one row per clutch.
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_indexes
    WHERE schemaname='public'
      AND indexname='uq_treated_clutches_one_per_clutch'
  ) THEN
    EXECUTE '
      CREATE UNIQUE INDEX uq_treated_clutches_one_per_clutch
        ON public.treated_clutches(clutch_instance_id)
    ';
  END IF;
END$$;

-- Trigger to auto-create the default treated_clutch (#0) on new clutches
CREATE OR REPLACE FUNCTION public.trg_clutch_default_treated()
RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM public.treated_clutches tc
    WHERE tc.clutch_instance_id = NEW.id
  ) THEN
    INSERT INTO public.treated_clutches (id, treated_clutch_code, clutch_instance_id, created_at)
    VALUES (
      gen_random_uuid(),
      COALESCE(NULLIF(NEW.clutch_instance_code,''),'CI') || '#0',
      NEW.id,
      now()
    );
  END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_clutch_default_treated ON public.clutch_instances;
CREATE TRIGGER trg_clutch_default_treated
AFTER INSERT ON public.clutch_instances
FOR EACH ROW EXECUTE FUNCTION public.trg_clutch_default_treated();

COMMIT;
