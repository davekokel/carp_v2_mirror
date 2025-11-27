BEGIN;

-- Drop and recreate the trigger function with the new code format
DROP TRIGGER IF EXISTS trg_tanks_from_fish_instances_v10 ON public.fish_instances_v10;
DROP FUNCTION IF EXISTS public.ensure_tank_for_fish_instance_v10();

CREATE FUNCTION public.ensure_tank_for_fish_instance_v10()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
  v_fish_code text;
  v_suffix    text;
BEGIN
  IF NEW.id IS NULL THEN
    RETURN NEW;
  END IF;

  -- if a tank already exists for this fish_instance, do nothing
  IF EXISTS (
    SELECT 1 FROM public.tanks t
    WHERE t.fish_instance_id = NEW.id
  ) THEN
    RETURN NEW;
  END IF;

  -- base fish_code (fall back to first 8 chars of UUID)
  v_fish_code := COALESCE(NEW.fish_code, substr(NEW.id::text, 1, 8));

  -- for now we assume one tank per fish instance, so suffix is always 001
  v_suffix := '001';

  INSERT INTO public.tanks (
    id,
    tank_code,
    location,
    status,
    volume_l,
    notes,
    created_at,
    fish_instance_id
  )
  VALUES (
    gen_random_uuid(),
    'TANK-' || v_fish_code || '-' || v_suffix,
    NULL,
    'active',
    NULL,
    NULL,
    COALESCE(NEW.created_at, now()),
    NEW.id
  );

  RETURN NEW;
END;
$$;

CREATE TRIGGER trg_tanks_from_fish_instances_v10
AFTER INSERT ON public.fish_instances_v10
FOR EACH ROW
EXECUTE FUNCTION public.ensure_tank_for_fish_instance_v10();

-- Backfill existing tank_code values to the new format
UPDATE public.tanks t
SET tank_code = 'TANK-' || COALESCE(fi.fish_code, substr(fi.id::text, 1, 8)) || '-001'
FROM public.fish_instances_v10 fi
WHERE fi.id = t.fish_instance_id;

COMMIT;
