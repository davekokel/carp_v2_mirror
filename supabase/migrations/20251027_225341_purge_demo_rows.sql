-- Purge any legacy/demo/backfill rows that can appear during strict replays.
-- Tight patterns to avoid touching real data; adjust if needed.
DO $$
BEGIN
  -- Delete clutch instances seeded off TP-... demo codes
  DELETE FROM public.clutch_instances ci
  USING public.cross_instances x
  WHERE ci.cross_instance_id = x.id
    AND x.cross_run_code LIKE 'CR(TP-%';

  -- Delete cross instances with demo TP-based codes
  DELETE FROM public.cross_instances x
  WHERE x.cross_run_code LIKE 'CR(TP-%';

  -- Delete tank_pairs that used demo TP-... codes
  DELETE FROM public.tank_pairs tp
  WHERE tp.tank_pair_code LIKE 'TP-%';

  -- Delete demo tanks with these well-known prefixes
  DELETE FROM public.tanks t
  WHERE t.tank_code LIKE 'TNK-MOM-%'
     OR t.tank_code LIKE 'TNK-DAD-%';
END$$;
