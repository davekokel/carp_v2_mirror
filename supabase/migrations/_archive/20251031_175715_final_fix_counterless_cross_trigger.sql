-- Finalize counterless cross run numbering: remove legacy artifacts, install correct function/trigger.

DO $prep$
DECLARE
  r RECORD;
BEGIN
  -- Drop *any* non-internal trigger on cross_instances whose name matches our old/new patterns.
  FOR r IN
    SELECT t.tgname
    FROM pg_trigger t
    WHERE t.tgrelid = 'public.cross_instances'::regclass
      AND NOT t.tgisinternal
      AND t.tgname ~ '^(trg_)?cross.*run|trg_cross_instances_'
  LOOP
    EXECUTE format('DROP TRIGGER IF EXISTS %I ON public.cross_instances', r.tgname);
  END LOOP;

  -- Drop any existing next_run_nn variants in public (any signature).
  FOR r IN
    SELECT (p.oid::regprocedure)::text AS sig
    FROM pg_proc p
    WHERE p.pronamespace = 'public'::regnamespace
      AND p.proname = 'next_run_nn'
  LOOP
    EXECUTE format('DROP FUNCTION IF EXISTS %s CASCADE', r.sig);
  END LOOP;

  -- Ensure cross_instances has run_nn column and uniqueness guard.
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
     WHERE table_schema='public' AND table_name='cross_instances' AND column_name='run_nn'
  ) THEN
    EXECUTE 'ALTER TABLE public.cross_instances ADD COLUMN run_nn integer';
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid='public.cross_instances'::regclass AND conname='uq_tank_pairs_run_nn'
  ) AND NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid='public.cross_instances'::regclass AND conname='uq_tankpair_run_nn'
  ) THEN
    -- Prefer stable name uq_tank_pairs_run_nn; tolerate older name if already present.
    EXECUTE 'ALTER TABLE public.cross_instances
             ADD CONSTRAINT uq_tank_pairs_run_nn UNIQUE (tank_pair_code, run_nn)';
  END IF;
END
$prep$;

-- Counterless next_run_nn: use md5() to derive a 64-bit advisory key, then MAX(run_nn)+1
CREATE OR REPLACE FUNCTION public.next_run_nn(p_tank_pair_code text)
RETURNS integer
LANGUAGE plpgsql
AS $$
DECLARE
  v integer;
  k bigint;
BEGIN
  -- lock on a stable 64-bit key per tank pair to serialize number assignment
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

-- Trigger: set run_nn if absent; always set cross_run_code from run_nn
CREATE OR REPLACE FUNCTION public.trg_cross_instances_set_code()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  IF NEW.run_nn IS NULL THEN
    NEW.run_nn := public.next_run_nn(NEW.tank_pair_code);
  END IF;

  IF NEW.cross_run_code IS NULL THEN
    -- Use TP-<pair>-NN format; change to 'CR-%s-%02s' if you prefer CR prefix.
    NEW.cross_run_code := format('TP-%s-%02s', NEW.tank_pair_code, NEW.run_nn);
  END IF;

  RETURN NEW;
END
$$;

-- Recreate the trigger with a single canonical name
CREATE TRIGGER trg_cross_instances_set_code
BEFORE INSERT ON public.cross_instances
FOR EACH ROW
EXECUTE FUNCTION public.trg_cross_instances_set_code();
