-- Migrate cross run numbering to data-derived run_nn (no tp_run_counters)
-- 1) Ensure cross_instances has run_nn and uniqueness on (tank_pair_code, run_nn)
DO $ddl$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='cross_instances' AND column_name='run_nn'
  ) THEN
    EXECUTE 'ALTER TABLE public.cross_instances ADD COLUMN run_nn integer';
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'uq_cross_instances_tpc_run'
  ) THEN
    -- Assumes cross_instances has tank_pair_code
    EXECUTE 'ALTER TABLE public.cross_instances
             ADD CONSTRAINT uq_cross_instances_tpc_run UNIQUE (tank_pair_code, run_nn)';
  END IF;
END
$ddl$;

-- 2) Create/replace next_run_nn() using advisory xact lock + MAX(run_nn)+1
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE OR REPLACE FUNCTION public.next_run_nn(p_tank_pair_code text)
RETURNS integer
LANGUAGE plpgsql
AS $fn$
DECLARE
  v integer;
  k bigint;
BEGIN
  -- derive a stable 64-bit key from tank_pair_code for per-pair serialization
  SELECT ('x' || substr(encode(digest(coalesce(p_tank_pair_code,''),'sha256'),1),1,16))::bit(64)::bigint INTO k;
  PERFORM pg_advisory_xact_lock(k);

  SELECT COALESCE(MAX(run_nn),0) + 1
    INTO v
    FROM public.cross_users_run_nn -- placeholder to avoid parse error if renamed
    -- REPLACED NEXT LINE IN RAISE NOTICE
  ;
  -- Actual select (split due to $$ quoting): 
  --   SELECT COALESCE(MAX(run_nn),0) + 1 FROM public.cross_instances WHERE tank_pair_code = p_tank_pair_code;

  RETURN (
    SELECT COALESCE(MAX(run_nn),0) + 1
    FROM public.cross_instances
    WHERE tank_pair_code = p_tank_pair_code
  );
END
$fn$;

-- 3) Trigger to set run_nn and cross_run_code on insert (if caller didn’t set)
CREATE OR REPLACE FUNCTION public.trg_cross_instances_set_code()
RETURNS trigger
LANGUAGE plpgsql
AS $trg$
BEGIN
  -- derive run_nn if missing
  IF NEW.run_nn IS NULL THEN
    NEW.run_nn := public.next_run_nn(NEW.tank_pair_code);
  END IF;

  -- fill cross_run_code if missing; pattern CR-<TP>-<2-digit seq>
  IF NEW.cross_run_code IS NULL THEN
    NEW.cross_run_code := format('CR-%s-%s',
      NEW.tank_pair_code,
      LPAD(NEW.run_nn::text, 2, '0')
    );
  END IF;

  RETURN NEW;
END
$trg$;

-- 4) Ensure our trigger is in place, remove any legacy ones that call tp_run_counters/make_cr_code
DO $trig$
DECLARE
  r RECORD;
BEGIN
  -- Drop legacy triggers on cross_instances that reference tp_run_counters / make_cr_code
  FOR r IN
    SELECT t.tgname, (p.oid::regprocedure)::text AS regproc
    FROM pg_trigger t
    JOIN pg_class c     ON c.oid = t.tgrelid
    JOIN pg_namespace n ON n.oid = c.relnamespace
    JOIN pg_proc p      ON p.oid = t.tgfoid
    WHERE NOT t.tgisinternal
      AND n.nspname='public' AND c.relname='cross_instances'
      AND ( pg_get_functiondef(p.oid) ILIKE '%tp_run_counters%'
            OR p.proname ILIKE '%make_cr_code%' )
  LOOP
    EXECUTE format('DROP TRIGGER IF EXISTS %I ON public.cross_instances', r.tgname);
    BEGIN
      EXECUTE format('DROP FUNCTION IF EXISTS %s CASCADE', r.regproc);
    EXCEPTION WHEN OTHERS THEN
      -- ignore if still referenced by something else
      NULL;
    END;
  END LOOP;

  -- Ensure our trigger exists and points to our function
  IF EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='trg_cross_instances_set_code' AND tgrelid='public.cross_instances'::regclass) THEN
    EXECUTE 'DROP TRIGGER IF EXISTS trg_cross_instances_set_code ON public.cross_instances';
  END IF;

  EXECUTE 'CREATE TRIGGER trg_cross_instances_set_code
           BEFORE INSERT ON public.cross_instances
           FOR EACH ROW
           EXECUTE FUNCTION public.trg_cRossz_instances_set_code()';
END
$trig$;

-- 5) Drop the counter tables if present (both public and trash)
DO $drop$
BEGIN
  IF to_regclass('public.tp_run_counters')    IS NOT NULL THEN
    EXECUTE 'DROP TABLE public.tp_run_counters CASCADE';
  END IF;
  IF to_regclass('trash_carp.tp_run_counters') IS NOT NULL THEN
    EXECUTE 'DROP TABLE trash_carp.tp_run_counters CASCADE';
  END IF;
END
$drop$;

-- NOTE: If you have a hard-coded make_cr_code() used elsewhere, consider migrating those callers
-- to rely on cross_instances.run_nn and/or call next_run_nn() explicitly.

CREATE OR REPLACE FUNCTION public.next_run_nn(p_tank_pair_code text)
RETURNS integer
LANGUAGE plpgsql
AS $fn$
DECLARE
  v integer;
  k bigint;
BEGIN
  SELECT ('x' || substr(encode(digest(coalesce(p_tank_pair_code,''),'sha256'),1),1,16))::bit(64)::bigint INTO k;
  PERFORM pg_advisory_xact_lock(k);

  SELECT COALESCE(MAX(run_nn),0) + 1 INTO v
  FROM public.cross_instances
  WHERE tank_pair_code = p_tank_pair_code;

  RETURN v;
END
$fn$;

-- Recreate the trigger with correct function name (typo-guard)
DROP TRIGGER IF EXISTS trg_cross_instances_set_code ON public.cross_instances;
CREATE TRIGGER trg_cross_instances_set_code
BEFORE INSERT ON public.cross_instances
FOR EACH ROW
EXECUTE FUNCTION public.trg_cross_instances_set_code();
