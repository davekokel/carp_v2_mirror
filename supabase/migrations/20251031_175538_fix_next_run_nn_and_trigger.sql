-- Fix next_run_nn/cross_instances trigger: remove bad encode(), set run_nn, keep counterless design.

DO $pre$
BEGIN
  -- Ensure cross_instances has run_nn & uniqueness (idempotent)
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='cross_instances' AND column_name='run_nn'
  ) THEN
    EXECUTE 'ALTER TABLE public.cross_instances ADD COLUMN run_nn integer';
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname='uq_tankpair_run_nn' AND conrelid='public.cross_instances'::regclass
  ) THEN
    EXECUTE 'ALTER TABLE public.cross_instances
             ADD CONSTRAINT uq_tankpair_run_nn UNIQUE (tank_pair_code, run_nn)';
  END IF;

  -- Drop any existing trigger so we can re-create cleanly
  IF EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='trg_cross_instances_set_code'
             AND tgrelid='public.cross_instances'::regclass) THEN
    EXECUTE 'DROP TRIGGER trg_cross_instances_set_code ON public.cross_instances';
  END IF;

  -- Drop any preexisting trigger functions with same name to avoid signature conflicts
  IF EXISTS (SELECT 1 FROM pg_proc WHERE proname='trg_cross_instances_set_code' AND pronamespace = 'public'::regnamespace) THEN
    EXECUTE 'DROP FUNCTION public.trg_cross_instances_set_code() CASCADE';
  END IF;

  -- Drop any legacy next_run_nn variants (wrong return type/signature)
  PERFORM 1 FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
   WHERE n.nspname='public' AND p.proname='next_run_nn';
  IF FOUND THEN
    FOR r IN SELECT (p.oid::regprocedure)::text AS sig
             FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
             WHERE n.nspname='public' AND p.proname='next_run_nn'
    LOOP
      EXECUTE format('DROP FUNCTION IF EXISTS %s CASCADE', r.sig);
    END LOOP;
  END IF;
END
$pre$;

-- Recreate counterless next_run_nn using md5(text) → 64-bit advisory key
CREATE OR REPLACE FUNCTION public.next_run_nn(p_tank_pair_code text)
RETURNS integer
LANGUAGE plpgsql
AS $$
DECLARE
  v integer;
  k bigint;
BEGIN
  -- Stable 64-bit key per tank_pair_code to serialize increments
  SELECT ('x' || substr(md5(coalesce(p_tank_pair_code,'')), 1, 16))::bit(64)::bigint
    INTO k;
  PERFORM pg_advisory_xact_lock(k);

  SELECT COALESCE(MAX(run_nn), 0) + 1
    INTO v
    FROM public.cross_instances
   WHERE tank_pair_code = p_tank_pair_code;

  RETURN v;
END
$$;

-- Trigger: set run_nn if missing; always set cross_run_code from run_nn
CREATE FUNCTION public.trg_cross_instances_set_code()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  IF NEW.run_nn IS NULL THEN
    NEW.run_nn := public.next_run_nn(NEW.tank_pair_code);
  END IF;

  IF NEW.cross_run_code IS NULL THEN
    -- Example: TP-2500003-01; adjust format if you prefer CR-… prefix:
    NEW.cross_run_code := format('%s-%02s', NEW.tank_pair_code, NEW.run_nn);
  END IF;

  RETURN NEW;
END
$$;

CREATE TRIGGER trg_cross_instances_set_on_insert
BEFORE INSERT ON public.cross_instances
FOR EACH ROW
EXECUTE FUNCTION public.trg_cross_instances_set_code();
