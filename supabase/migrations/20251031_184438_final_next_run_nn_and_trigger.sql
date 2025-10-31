DO $$
DECLARE
  r record;
BEGIN
  -- Drop any next_run_nn variants in public (any signature)
  FOR r IN
    SELECT (p.oid::regprocedure)::text AS sig
    FROM pg_proc p
    WHERE p.pronamespace='public'::regnamespace
      AND p.proname='next_run_nn'
  LOOP
    EXECUTE format('DROP FUNCTION IF EXISTS %s CASCADE', r.sig);
  END LOOP;

  -- Drop any existing cross_instances triggers and trigger func
  FOR r IN
    SELECT t.tgname
    FROM pg_trigger t
    WHERE t.tgrelid='public.cross_instances'::regclass AND NOT t.tgisinternal
  LOOP
    EXECUTE format('DROP TRIGGER IF EXISTS %I ON public.cross_instances', r.tgname);
  END LOOP;

  IF EXISTS (SELECT 1 FROM pg_proc WHERE pronamespace='public'::regnamespace AND proname='trg_cross_instances_set_code') THEN
    EXECUTE 'DROP FUNCTION public.trg_cross_instances_set_code() CASCADE';
  END IF;

  -- Ensure run_nn and unique constraint
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='cross_instances' AND column_name='run_nn'
  ) THEN
    EXECUTE 'ALTER TABLE public.cross_instances ADD COLUMN run_nn integer';
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
     WHERE conrelid='public.cross_instances'::regclass
       AND conname IN ('uq_tankpair_run_nn','uq_tank_pairs_run_nn')
  ) THEN
    EXECUTE 'ALTER TABLE public.cross_instances
             ADD CONSTRAINT uq_tankpair_run_nn UNIQUE (tank_pair_code, run_nn)';
  END IF;
END
$$;

CREATE OR REPLACE FUNCTION public.next_run_nn(p_tank_pair_code text)
RETURNS integer
LANGUAGE plpgsql
AS $$
DECLARE v integer; k bigint;
BEGIN
  SELECT ('x'||substr(md5(coalesce(p_tank_pair_code,'')),1,16))::bit(64)::bigint INTO k;
  PERFORM pg_advisory_xact_lock(k);
  SELECT COALESCE(MAX(run_nn),0)+1 INTO v
  FROM public.cross_instances
  WHERE tank_pair_code=p_tank_pair_code;
  RETURN v;
END
$$;

CREATE OR REPLACE FUNCTION public.trg_cross_instances_set_code()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  IF NEW.run_nn IS NULL THEN
    NEW.run_nn := public.next_run_nn(NEW.tank_pair_code);
  END IF;
  IF NEW.cross_run_code IS NULL THEN
    NEW.cross_run_code := format('TP-%s-%02s', NEW.tank_pair_code, NEW.run_nn);
  END IF;
  RETURN NEW;
END
$$;

CREATE TRIGGER trg_cross_instances_set_code
BEFORE INSERT ON public.cross_instances
FOR EACH ROW
EXECUTE FUNCTION public.trg_cross_instances_set_code();
