DO $$
BEGIN
  -- Delete in dependency order (children first)
  DELETE FROM public.clutch_instances;
  DELETE FROM public.cross_instances;

  -- If you have a fish_tank_memberships table, clear it before tanks
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema='public' AND table_name='fish_tank_memberships'
  ) THEN
    DELETE FROM public.fish_tank_memberships;
  END IF;

  DELETE FROM public.tank_pairs;
  DELETE FROM public.tanks;
END$$;
