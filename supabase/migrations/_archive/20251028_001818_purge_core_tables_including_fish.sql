DO $$
BEGIN
  -- child tables first (adjust if names differ)
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='fish_tank_memberships') THEN
    DELETE FROM public.fish_tank_memberships;
  END IF;

  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='fish_transgene_alleles') THEN
    DELETE FROM public.fish_transgene_alleles;
  END IF;

  -- cross/ clutch are separate entities; keep them empty too
  DELETE FROM public.clutch_instances;
  DELETE FROM public.cross_instances;

  -- pairs & tanks
  DELETE FROM public.tank_pairs;
  DELETE FROM public.tanks;

  -- finally, fish
  DELETE FROM public.fish;
END$$;
