DO $$
DECLARE r record;
BEGIN
  -- Drop all non-internal triggers on cross_instances
  FOR r IN
    SELECT t.tgname
    FROM pg_trigger t
    WHERE t.tgrelid='public.cross_instances'::regclass
      AND NOT t.tgisinternal
  LOOP
    EXECUTE format('DROP TRIGGER %I ON public.cross_instances', r.tgname);
  END LOOP;

  -- Ensure the function exists (counterless)
  CREATE OR REPLACE FUNCTION public.next_run_nn(p_tank_pair_code text)
  RETURNS integer LANGUAGE plpgsql AS $fn$
  DECLARE v integer; k bigint;
  BEGIN
    SELECT ('x'||substr(md5(coalesce(p_tank_pair_code,'')),1,16))::bit(64)::bigint INTO k;
    PERFORM pg_advisory_xact_lock(k);
    SELECT COALESCE(MAX(run_nn),0)+1 INTO v
    FROM public.cross_instances
    WHERE tank_pair_code=p_tank_pair_code;
    RETURN v;
  END $fn$;

  CREATE OR REPLACE FUNCTION public.trg_cross_instances_set_code()
  RETURNS trigger LANGUAGE plpgsql AS $trg$
  BEGIN
    IF NEW.run_nn IS NULL THEN
      NEW.run_nn := public.next_run_nn(NEW.tank_pair_code);
    END IF;
    IF NEW.cross_run_code IS NULL THEN
      NEW.cross_run_code := format('TP-%s-%02s', NEW.tank_pair_code, NEW.run_nn);
    END IF;
    RETURN NEW;
  END $trg$;

  -- Create one canonical BEFORE trigger
  EXECUTE 'CREATE TRIGGER trg_cross_instances_set_code
           BEFORE INSERT ON public.cross_instances
           FOR EACH ROW
           EXECUTE FUNCTION public.trg_cross_instances_set_code()';
END
$$;

-- Backfill any historical rows that somehow missed codes
UPDATE public.cross_instances ci
SET run_nn = COALESCE(ci.run_nn, public.next_run_nn(ci.tank_pair_code)),
    cross_run_code = COALESCE(ci.cross_run_code, format('TP-%s-%02s', ci.tank_pair_code, COALESCE(ci.run_nn,1)))
WHERE ci.run_nn IS NULL OR ci.cross_run_code IS NULL;
