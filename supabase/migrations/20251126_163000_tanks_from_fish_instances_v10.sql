BEGIN;

-- Optional: drop old trigger/function if they exist from earlier experiments
DO $$
BEGIN
  IF to_regproc('public.ensure_tank_for_fish_instance_v10()') IS NOT NULL THEN
    DROP TRIGGER IF EXISTS trg_tanks_from_fish_instances_v10 ON public.fish_instances_v10;
    DROP FUNCTION IF EXISTS public.ensure_tank_for_fish_instance_v10();
  END IF;
END $$;

-- Function: ensure there is exactly one tank row per fish_instance_v10
CREATE FUNCTION public.ensure_tank_for_fish_instance_v10()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  IF NEW.id IS NULL THEN
    RETURN NEW;
  END IF;

  -- If a tank already exists for this fish_instance, do nothing
  IF EXISTS (
    SELECT 1 FROM public.tanks t
    WHERE t.fish_instance_id = NEW.id
  ) THEN
    RETURN NEW;
  END IF;

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
    -- simple default tank code: prefix + fish_code; adjust pattern if you prefer
    'TNK-' || COALESCE(NEW.fish_code, substr(NEW.id::text, 1, 8)),
    NULL,          -- location
    'active',      -- default status
    NULL,          -- volume_l
    NULL,          -- notes
    COALESCE(NEW.created_at, now()),
    NEW.id
  );

  RETURN NEW;
END;
$$;

-- Trigger: run the function after each insert into fish_instances_v10
CREATE TRIGGER trg_tanks_from_fish_instances_v10
AFTER INSERT ON public.fish_instances_v10
FOR EACH ROW
EXECUTE FUNCTION public.ensure_tank_for_fish_instance_v10();

-- One-time backfill: create tanks for any existing fish_instances_v10 that lack one
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
SELECT
  gen_random_uuid() AS id,
  'TNK-' || COALESCE(fi.fish_code, substr(fi.id::text, 1, 8)) AS tank_code,
  NULL::text    AS location,
  'active'      AS status,
  NULL::numeric AS volume_l,
  NULL::text    AS notes,
  COALESCE(fi.created_at, now()) AS created_at,
  fi.id         AS fish_instance_id
FROM public.fish_instances_v10 fi
LEFT JOIN public.tanks t
  ON t.fish_instance_id = fi.id
WHERE t.id IS NULL;

COMMIT;
