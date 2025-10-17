BEGIN;

-- 1) Replace trigger function to avoid double "XR-"
CREATE OR REPLACE FUNCTION public.trg_clutch_instances_alloc_seq()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
  v_next int;
  v_run text;
BEGIN
  IF NEW.seq IS NULL OR NEW.seq = 0 THEN
    INSERT INTO public.clutch_instance_seq(cross_instance_id, last)
    VALUES (NEW.cross_instance_id, 0)
    ON CONFLICT (cross_instance_id) DO UPDATE
      SET last = public.clutch_instance_seq.last + 1
    RETURNING last INTO v_next;

    NEW.seq := v_next::smallint;
  END IF;

  -- v_run already looks like "XR-2510001"; do NOT add another "XR-"
  SELECT cross_run_code INTO v_run
  FROM public.cross_instances
  WHERE id = NEW.cross_instance_id;

  NEW.clutch_instance_code := v_run || '-' || lpad(NEW.seq::text, 2, '0');
  RETURN NEW;
END
$$;

-- Ensure trigger is present and points at the latest function
DROP TRIGGER IF EXISTS clutch_instances_alloc_seq ON public.clutch_instances;
CREATE TRIGGER clutch_instances_alloc_seq
BEFORE INSERT ON public.clutch_instances
FOR EACH ROW
EXECUTE FUNCTION public.trg_clutch_instances_alloc_seq();

-- 2) Backfill existing rows with "XR-XR..." → strip the first "XR-"
UPDATE public.clutch_instances
SET clutch_instance_code = substring(clutch_instance_code FROM 4)
WHERE clutch_instance_code LIKE 'XR-XR%';

COMMIT;
