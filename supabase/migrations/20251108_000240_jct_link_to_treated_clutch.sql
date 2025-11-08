BEGIN;

-- 1) Add treated_clutch_id
ALTER TABLE public.join_clutch_treatments
  ADD COLUMN IF NOT EXISTS treated_clutch_id uuid REFERENCES public.treated_clutches(id) ON DELETE CASCADE;

-- 2) Backfill: create one default group per clutch_instance that has treatments,
--    then link existing rows to that default.
WITH have_tx AS (
  SELECT DISTINCT jct.clutch_instance_id
  FROM public.join_clutch_treatments jct
  WHERE jct.treated_clutch_id IS NULL
),
mk_default AS (
  INSERT INTO public.treated_clutches (clutch_instance_id, label, created_by)
  SELECT ht.clutch_instance_id, 'default', 'backfill'
  FROM have_tx ht
  RETURNING id, clutch_instance_id
)
UPDATE public.join_clutch_treatments j
SET treated_clutch_id = md.id
FROM mk_default md
WHERE j.treated_clutch_id IS NULL
  AND j.clutch_instance_id = md.clutch_instance_id;

-- 3) Unique key now applies per treated_clutch_id (not just per clutch instance)
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid='public.join_clutch_treatments'::regclass
      AND conname='uq_jct_by_instance_kind_code'
  ) THEN
    EXECUTE 'ALTER TABLE public.join_clutch_treatments DROP CONSTRAINT uq_jct_by_instance_kind_code';
  END IF;
END$$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid='public.join_clutch_treatments'::regclass
      AND conname='uq_jct_by_group_kind_code'
  ) THEN
    EXECUTE 'ALTER TABLE public.join_clutch_treatments
             ADD CONSTRAINT uq_jct_by_group_kind_code
             UNIQUE (treated_clutch_id, treatment_type_norm, treatment_code_norm)';
  END IF;
END$$;

-- 4) When a row is inserted without treated_clutch_id,
--    auto-attach to/create the per-clutch "default" group.
CREATE OR REPLACE FUNCTION public.jct_bi_assign_group()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
  v_group_id uuid;
BEGIN
  IF NEW.treated_clutch_id IS NOT NULL THEN
    RETURN NEW;
  END IF;

  -- find existing default group for this clutch_instance
  SELECT id INTO v_group_id
  FROM public.treated_clutches
  WHERE clutch_instance_id = NEW.clutch_instance_id
  ORDER BY created_at ASC
  LIMIT 1;

  IF v_group_id IS NULL THEN
    INSERT INTO public.treated_clutches (clutch_instance_id, label, created_by)
    VALUES (NEW.clutch_instance_id, 'default', COALESCE(NEW.created_by,'')) 
    RETURNING id INTO v_group_id;
  END IF;

  NEW.treated_clutch_id := v_group_id;
  RETURN NEW;
END
$$;

DROP TRIGGER IF EXISTS trg_jct_bi_assign_group ON public.join_clutch_treatments;
CREATE TRIGGER trg_jct_bi_assign_group
BEFORE INSERT ON public.join_clutch_treatments
FOR EACH ROW EXECUTE FUNCTION public.jct_bi_assign_group();

COMMIT;
