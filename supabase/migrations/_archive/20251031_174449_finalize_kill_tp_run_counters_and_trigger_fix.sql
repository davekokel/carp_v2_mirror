-- Finalize counterless cross run numbering on cross_instances

-- 0) Ensure schema on cross_instances (run_nn + uniqueness)
DO $ddl$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='cross_instances' AND column_name='run_nn'
  ) THEN
    EXECUTE 'ALTER TABLE public.cross_instances ADD COLUMN run_nn integer';
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname='uq_tankpair_run_nn' AND conrelid='public.cross_instances'::regclass
  ) THEN
    -- prefer short, stable name
    BEGIN
      EXECUTE 'ALTER TABLE public.cross_instances ADD CONSTRAINT uq_tankpair_run_nn UNIQUE (tank_pair_code, run_nn)';
    EXCEPTION WHEN duplicate_object THEN
      NULL;
    END;
  END IF;
END
$ddl$;

-- 1) Drop any non-internal triggers on cross_instances that call legacy run code funcs
DO $drop_trg$
DECLARE
  r RECORD;
BEGIN
  FOR r IN
    SELECT t.tgname, (p.oid::regprocedure)::text AS regproc
    FROM pg_trigger t
    JOIN pg_class c     ON c.oid = t.tgrelid
    JOIN pg_namespace n ON n.oid = c.relnamespace
    JOIN pg_proc p      ON p.oid = t.tgfoid
    WHERE NOT t.tgisinternal
      AND n.nspname='public'
      AND c.relname='cross_instances'
      AND (
           p.proname ILIKE '%make\_cr\_code%'
        OR p.proname ILIKE '%next\_run\_%'
        OR pg_get_functiondef(p.oid) ILIKE '%tp\_run\_counters%'
          )
  LOOP
    EXECUTE format('DROP TRIGGER IF EXISTS %I ON public.cross_instances', r.tgname);
    -- don't drop the function here; we'll drop all variants in step 2
  END LOOP;
END
$drop_trg$;

-- 2) Drop any existing next_run_nn variants in public (regardless of return type/signature)
DO $drop_fn$
DECLARE
  sig text;
BEGIN
  FOR sig IN
    SELECT (p.oid::regprocedure)::text
    FROM pg_proc p
    JOIN pg_namespace n ON n.oid=p.pronamespace
    WHERE n.nspname='public' AND p.proname='next_run_nn'
  LOOP
    EXECUTE format('DROP FUNCTION IF EXISTS %s CASCADE', sig);
  END LOOP;
END
$drop_fn$;

-- 3) (Re)create advisory-locked next_run_nn() that derives next sequence from existing rows
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE OR REPLACE FUNCTION public.next_run_nn(p_tank_pair_code text)
RETURNS integer
LANGUAGE plpgsql
AS $fn$
DECLARE
  v integer;
  k bigint;
BEGIN
  -- serialize per tank_pair_code using a stable 64-bit key
  SELECT ('x' || substr(encode(digest(coalesce(p_tank_pair_code,''),'sha256'),1),1,16))::bit(64)::bigint
    INTO k;
  PERFORM pg_advisory_xact_lock(k);

  SELECT COALESCE(MAX(run_nn), 0) + 1
    INTO v
    FROM public.cross_instances
   WHERE tank_pair_code = p_tank_pair_code;

  RETURN v;
END
$fn$;

-- 4) (Re)create trigger that fills run_nn and cross_run_code
CREATE OR REPLACE FUNCTION public.trg_cross_instances_set_code()
RETURNS trigger
LANGUAGE plpgsql
AS $trg$
BEGIN
  IF NEW.run_ln IS NOT NULL THEN -- typo guard from older versions
    NEW.run_nn := NEW.run_ln;
  END IF;

  IF NEW.run_nn IS NULL THEN
    NEW.run_nn := public.next_run_nn(NEW.tank_pair_code);
  END IF;

  IF NEW.cross_run_code IS NULL THEN
    NEW.cross_run_code := format('CR-%s-%s', NEW.tank_pair_code, lpad(NEW.run_nn::text, 2, '0'));
  END IF;

  RETURN NEW;
END
$trg$;

DROP TRIGGER IF EXISTS trg_cross_instances_set_code ON public.cross_instances;
CREATE TRIGGER trg_cross_instances_set_code
BEFORE INSERT ON public.cross_instances
FOR EACH ROW
EXECUTE FUNCTION public.trg_cross_instances_set_code();

-- 5) Remove tp_run_counters (public/trash) if present
DO $drop_tbl$
BEGIN
  IF to_regclass('public.tp_run_counters') IS NOT NULL THEN
    EXECUTE 'DROP TABLE public.tp_run_counters CASCADE';
  END IF;
  IF to_regclass('trash_carp.tp_run_counters') IS NOT NULL THEN
    EXECUTE 'DROP TABLE public.tp_run_counters CASCADE';
  END IF;
END
$drop_tbl$;
