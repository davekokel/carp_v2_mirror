BEGIN;

CREATE OR REPLACE FUNCTION public.trg_fish_instance_auto_tank()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
  v_tank_id uuid;
BEGIN
  -- existing logic to determine v_tank_id goes here.
  -- I'm not changing that part; only the INSERT.

  -- NOTE: you should paste the full original function body here and
  -- replace only the INSERT INTO tank_memberships line with the one below.

  INSERT INTO public.tank_memberships (tank_id, fish_id, role, started_at)
  VALUES (v_tank_id, NEW.id, 'resident', now());

  RETURN NEW;
END;
$$;

COMMIT;
