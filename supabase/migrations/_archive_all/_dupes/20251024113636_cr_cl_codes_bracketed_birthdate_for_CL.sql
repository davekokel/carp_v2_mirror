-- Bracketed codes (Option 1) with CL using *birth date*:
--   cross_instances.cross_run_code       : CR({TP})(YYMMDD_run)(NN)
--   clutch_instances.clutch_instance_code: CL({TP})(YYMMDD_birth)(NN)
-- Where:
--   {TP}   = public.tank_pairs.tank_pair_code for NEW.tank_pair_id
--   YYMMDD_run   = to_char(cross_date, 'YYMMDD')
--   YYMMDD_birth = to_char(birthday, 'YYMMDD')  -- defaults to cross_date + 1 day if NULL
--   NN     = 2-digit per-(tank_pair_id,cross_date) sequence, copied from CR into CL
-- This script:
--   * ensures columns and UUID defaults exist
--   * (re)creates BEFORE INSERT triggers to auto-assign codes
--   * adds CHECK constraints & unique indexes
--   * backfills existing data to the new shapes

BEGIN;

-- 0) Ensure pgcrypto for gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- 1) Ensure cross_instances.cross_run_code column & id default
DO $m$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='cross_instances' AND column_name='cross_run_code'
  ) THEN
    ALTER TABLE public.cross_instances ADD COLUMN cross_run_code text;
  END IF;

  -- Make sure 'id' has a default UUID (ignore if already set or not applicable)
  BEGIN
    ALTER TABLE public.cross_instances ALTER COLUMN id SET DEFAULT gen_random_uuid();
  EXCEPTION WHEN OTHERS THEN
    NULL;
  END;
END
$m$;

-- 2) CR code trigger: CR({TP})(YYMMDD_run)(NN)
DROP TRIGGER IF EXISTS trg_cross_instances_set_code ON public.cross_instances;
DROP FUNCTION IF EXISTS public.tg_cross_instances_set_code();

CREATE OR REPLACE FUNCTION public.tg_cross_instances_set_code()
RETURNS trigger
LANGUAGE plpgsql
AS $fn$
DECLARE
  tp_code text;
  ymd text;
  next_seq int;
  seq_text text;
BEGIN
  IF NEW.cross_run_code IS NULL OR NEW.cross_run_code !~ '^CR\([A-Z0-9-]+\)\([0-9]{6}\)\([0-9]{2}\)$' THEN
    SELECT t.tank_pair_code INTO tp_code
    FROM public.tank_pairs t
    WHERE t.id = NEW.tank_pair_id;

    IF tp_code IS NULL THEN
      RAISE EXCEPTION 'No matching tank_pair_code for tank_pair_id=%', NEW.tank_pair_id;
    END IF;

    IF NEW.cross_date IS NULL THEN
      RAISE EXCEPTION 'cross_date must be set to generate cross_run_code';
    END IF;

    ymd := to_char(NEW.cross_date, 'YYMMDD');

    SELECT COALESCE(MAX( (substring(ci.cross_run_code from '\(([0-9]{2})\)$'))::int ), 0) + 1
      INTO next_seq
    FROM public.cross_instances ci
    WHERE ci.tank_pair_id = NEW.tank_pair_id
      AND ci.cross_date   = NEW.cross_date
      AND ci.cross_run_code ~ '^CR\([A-Z0-9-]+\)\([0-9]{6}\)\([0-9]{2}\)$';

    seq_text := lpad(next(next_seq)::text, 2, '0');
    NEW.cross_run_code := format('CR(%s)(%s)(%s)', tp_code, ymd, seq_text);
  END IF;

  RETURN NEW;
END
$fn$;

CREATE TRIGGER trg_cross_instances_set_code
BEFORE INSERT ON public.cross_instances
FOR EACH ROW
EXECUTE FUNCTION public.tg_cross_instances_set_code();

-- Enforce CR code shape & uniqueness
DO $m$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.table_constraints
    WHERE table_schema='public' AND table_name='cross_instances' AND constraint_name='cross_run_code_shape'
  ) THEN
    ALTER TABLE public.cross_instances DROP CONSTRAINT cross_run_code_link_shape;
  END IF;
END
$m$;

ALTER TABLE public.cross_instances
  ADD CONSTRAINT cross_run_code_shape
  CHECK (cross_run_code ~ '^CR\([A-Z0-9-]+\)\([0-9]{6}\)\([0-9]{2}\)$');

CREATE UNIQUE INDEX IF NOT EXISTS uq_cross_instances_run_code
  ON public.cross_instances (cross_run_code);

-- 3) Ensure clutch_instances columns & default birthday trigger (birth = cross_date + 1 day)
DO $m$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='clutch_instances' AND column_name='clutch_instance_code'
  ) THEN
    ALTER TABLE public.clutch_instances ADD COLUMN clutch_instance_code text;
  END IF;

  BEGIN
    ALTER TABLE public.clutch_instances ALTER COLUMN id SET DEFAULT gen_random_uuid();
  EXCEPTION WHEN OTHERS THEN
    NULL;
  END;
END
$m$;

-- Default birthday from cross_date+1d if missing and linked to a cross
DROP TRIGGER IF EXISTS trg_clutch_instances_default_bday ON public.clutch_instances;
DROP FUNCTION IF EXISTS public.tg_clutch_instances_default_bday();

CREATE OR REPLACE FUNCTION public.tg_clutch_instances_default_bday()
RETURNS trigger
LANGUAGE plpgsql
AS $fn$
DECLARE
  d date;
BEGIN
  IF NEW.birthday IS NULL AND NEW.cross_instance_id IS NOT NULL THEN
    SELECT ci.cross_date INTO d FROM public.cross_instances ci WHERE ci.id = NEW.cross_instance_id;
    IF d IS NOT NULL THEN
      NEW.birthday := d + INTERVAL '1 day';
    END IF
  END IF;
  RETURN NEW;
END
$fn$;

CREATE TRIGGER trg_clutch_instances_default_bday
BEFORE INSERT ON public.clutch_instances
FOR EACH ROW
EXECUTE FUNCTION public.tg_clutch_instances_default_bday();

-- 4) CL code trigger: CL({TP})(YYMMDD_birth)(NN) where NN mirrors CR’s NN
DROP TRIGGER IF EXISTS trg_clutch_instances_set_code ON public.clutch_instances;
DROP FUNCTION IF EXISTS public.tg_clutch_instances_set_code();

CREATE OR REPLACE FUNCTION public.tg_clutch_instances_set_code()
RETURNS trigger
LANGUAGE plpgsql
AS $fn$
DECLARE
  tp_code text;
  run_code text;
  run_date date;
  seq_text text;
  birth_d  date;
BEGIN
  IF NEW.clutch_instance_code IS NOT NULL THEN
    RETURN NEW;
  END IF;

  IF NEW.cross_instance_id IS NULL THEN
    -- nothing to derive from; you can enforce NOT NULL cross link if needed
    RETURN NEW;
  END IF;

  SELECT ci.cross_run_code, ci.cross_date, tp.tank_pair_code
    INTO run_code, run_date, tp_code
  FROM public.cross_instances ci
  JOIN public.tank_pairs tp ON tp.id = ci.tank_pair_id
  WHERE ci.id = NEW.cross_instance_id;

  IF run_code IS NULL THEN
    RETURN NEW;
  END IF;

  -- parse NN from CR(...)(...)(NN)
  SELECT substring(run_code from '\(([0-9]{2})$') INTO seq_text;

  -- birthday: defaulted earlier; use it if present, else cross_date+1
  birth_d := COALESCE(NEW.birthday, run_date + INTERVAL '1 day');

  NEW.clutch_instance_code :=
    format('CL(%s)(%s)(%s)', tp_code, to_char(birth_d, 'YYMMDD'), COALESCE(seq_text, lpad('1', 2, '0')));

  RETURN NEW;
END
$fn$;

CREATE TRIGGER trg_clutch_instances_set_code
BEFORE INSERT ON public.clutch_instances
FOR EACH ROW
EXECUTE FUNCTION public.tg_clutch_instances_set_code();

-- Enforce CL code shape & uniqueness
DO $m$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.table_constraints
    WHERE table_schema='public' AND table_name='clutch_instances' AND constraint_name='clutch_instance_code_shape'
  ) THEN
    ALTER TABLE public.clutch_instances DROP CONSTRAINT clutch_instance_code_shape;
  END IF;
END
$m$;

ALTER TABLE public.clutch_instances
  ADD CONSTRAINT clutch_instance_code_shape
  CHECK (clutch_instance_code ~ '^CL\([A-Z0-9-]+\)\([0-9]{6}\)\([0-9]{2}\)$');

CREATE UNIQUE INDEX IF NOT EXISTS uq_clutch_instance_code
  ON public.clutch_instances (clutch_instance_code);

-- 5) Backfill existing rows to new shapes

-- Backfill CR codes to CR({TP})(YYMMDD_run)(NN)
WITH src AS (
  SELECT
      ci.id,
      tp.tank_pair_code,
      ci.cross_date,
      COALESCE(
        NULLIF((substring(ci.cross_run_code from '\(([0-9]{2})\)$'))::int, NULL),
        ROW_NUMBER() OVER (PARTITION BY ci.tank_pair_id, ci.cross_date ORDER BY ci.created_at)
      ) AS seqnum
  FROM public.cross_instances ci
  LEFT JOIN public.tank_pairs tp ON tp.id = ci.tank_pair_id
)
UPDATE public.cross_instances c
SET cross_run_code = format('CR(%s)(%s)(%s)',
                            s.tank_pair_code,
                            to_char(s.cross_date, 'YYMMDD'),
                            lpad(s.seqnum::text, 2, '0'))
FROM src s
WHERE c.id = s.id
  AND (c.cross_run_code IS NULL OR c.cross_run_code !~ '^CR\([A-Z0-9-]+\)\([0-9]{6}\)\([0-9]{2}\)$');

-- Backfill CL birthday from linked cross_date+1 if missing
UPDATE public.clutch_instances cl
SET    birthday = ci.cross_date + INTERVAL '1 day'
FROM   public.cross_instances ci
WHERE  cl.cross_instance_id = ci.id
  AND  cl.birthday IS NULL;

-- Backfill CL codes to CL({TP})(YYMMDD_birth)(NN), using CR’s NN
WITH jc AS (
  SELECT
      cl.id,
      tp.tank_pair_code,
      COALESCE(cl.birthday, ci.cross_date + INTERVAL '1 day') AS bday,
      substring(ci.cross_run_code from '\(([0-9]{2})\)$') AS seq2
  FROM public.clutch_instances cl
  JOIN public.cross_instances ci ON ci.id = cl.cross_instance_id
  LEFT JOIN public.tank_pairs tp ON tp.id = ci.tank_pair_id
)
UPDATE public.clutch_instances c
SET    clutch_instance_code = format('CL(%s)(%s)(%s)',
                                     jc.tank_pair_code,
                                     to_char(jc.bday, 'YYMMDD'),
                                     COALESCE(jc.seq2, lpad('1',2,'0')))
FROM   jc
WHERE  c.id = jc.id
  AND (c.clutch_instance_code IS NULL OR c.clutch_instance_code !~ '^CL\([A-Z0-9-]+\)[(][0-9]{6}[)]\([0-9]{2}\)$');

COMMIT;
