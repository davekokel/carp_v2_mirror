-- Unified, date-free codes:
--   cross_instances.cross_code       = 'CX('|| tank_pair_code ||')('|| NN ||')'
--   clutch_instances.clutch_code     = same as linked cross_code
-- Per-TP NN is monotonic (01,02,...) independent of date; time lives in columns.

BEGIN;

-- Ensure pgcrypto for gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- 1) Ensure new columns exist (no-op if present)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='cross_instances' AND column_name='cross_code'
  ) THEN
    ALTER TABLE public.cross_instances ADD COLUMN cross_code text;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='clutch_instances' AND column_name='clutch_code'
  ) THEN
    ALTER TABLE public.clutch_instances ADD COLUMN clutch_code text;
  END IF;

  -- Set UUID default on id columns if not already (safe to ignore failure)
  BEGIN
    ALTER TABLE public.cross_instances  ALTER COLUMN id SET DEFAULT gen_random_uuid();
  EXCEPTION WHEN OTHERS THEN NULL; END;
  BEGIN
    ALTER TABLE public.clutch_instances ALTER COLUMN id SET DEFAULT gen_random_uuid();
  EXCEPTION WHEN OTHERS THEN NULL; END;
END$$;

COMMIT;

-- 2) Triggers
BEGIN;

-- 2a) Cross: assign CX({TP})(NN) before insert
DROP TRIGGER IF EXISTS trg_cross_instances_set_cx_code ON public.cross_instances;
DROP FUNCTION IF EXISTS public.tg_cross_instances_set_cx_code();

CREATE FUNCTION public.tg_cross_instances_set_cx_code()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
  tp_code text;
  nn int;
  nn_txt text;
  last_nn int;
BEGIN
  -- Require a tank_pair_id
  IF NEW.tank_pair_id IS NULL THEN
    RAISE EXCEPTION 'cross_instances.tank_pair_id must be set to assign CX code';
  END IF;

  -- Fetch the human TP code
  SELECT t.tank_pair_code INTO tp_code
  FROM public.tank_pairs t
  WHERE t.id = NEW.tank_pair_id;

  IF tp_code IS NULL THEN
    RAISE EXCEPTION 'No tank_pair_code found for tank_pair_id=%', NEW.tank_pair_id;
  END IF;

  -- Only assign if missing or malformed
  IF NEW.cross_code IS NULL OR NEW.cross_code !~ '^CX\([A-Z0-9-]+\)\([0-9]{2,}\)$' THEN
    -- Compute next NN for this tank_pair_id
    SELECT COALESCE(MAX((substring(ci.cross_code from '\(([0-9]{2,})\)$'))::int), 0)
      INTO last_nn
    FROM public.cross_instances ci
    WHERE ci.tank_pair_id = NEW.tank_pair_id
      AND ci.cross_code ~ '\([0-9]{2,}\)$';

    nn := last_nn + 1;
    nn_txt := lpad(nn::text, 2, '0');
    NEW.cross_code := format('CX(%s)(%s)', tp_code, nn_txt);
  END IF;

  RETURN NEW;
END;
$$;

CREATE TRIGGER trg_cross_instances_set_cx_code
BEFORE INSERT ON public.cross_instances
FOR EACH ROW
EXECUTE FUNCTION public.tg_cross_instances_set_cx_code();

-- 2b) Clutch: default birthday, and assign clutch_code = linked cross.cross_code
DROP TRIGGER IF EXISTS trg_clutch_instances_default_birth ON public.clutch_instances;
DROP FUNCTION IF EXISTS public.tg_clutch_instances_default_birth();

CREATE FUNCTION public.tg_clutch_instances_default_birth()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
  d date;
BEGIN
  IF NEW.birthday IS NULL AND NEW.cross_instance_id IS NOT NULL THEN
    SELECT ci.cross_date INTO d
    FROM public.cross_instances ci WHERE ci.id = NEW.cross_instance_id;
    IF d IS NOT NULL THEN
      NEW.birthday := d + INTERVAL '1 day';
    END IF;
  END IF;
  RETURN NEW;
END;
$$;

CREATE TRIGGER trg_clutch_instances_default_birth
BEFORE INSERT ON public.clutch_instances
FOR EACH ROW
EXECUTE FUNCTION public.tg_clutch_instances_default_birth();

DROP TRIGGER IF EXISTS trg_clutch_instances_set_cx_code ON public.clutch_instances;
DROP FUNCTION IF EXISTS public.tg_clutch_instances_set_cx_code();

CREATE FUNCTION public.tg_clutch_instances_set_cx_code()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
  cx text;
BEGIN
  -- Only on insert; rely on link to cross
  IF NEW.cross_instance_id IS NULL THEN
    RETURN NEW;
  END IF;

  IF NEW.clutch_code IS NULL OR NEW.clutch_code !~ '^CX\([A-Z0-9-]+\)\([0-9]{2,}\)$' THEN
    SELECT cross_code INTO cx FROM public.cross_instances WHERE id = NEW.cross_instance_id;
    IF cx IS NOT NULL THEN
      NEW.clutch_code := cx;
    END IF;
  END IF;

  RETURN NEW;
END;
$$;

CREATE TRIGGER trg_clutch_instances_set_cx_code
BEFORE INSERT ON public.clutch_instances
FOR EACH ROW
EXECUTE FUNCTION public.tg_clutch_instances_set_cx_code();

COMMIT;

-- 3) Constraints & indexes
BEGIN;

-- Shape constraints (date-free unified code)
ALTER TABLE public.cross_instances
  DROP CONSTRAINT IF EXISTS cross_instances_cx_shape,
  ADD  CONSTRAINT cross_instances_cx_shape
  CHECK (cross_code ~ '^CX\([A-Z0-9-]+\)\([0-9]{2,}\)$');

ALTER TABLE public.clutch_instances
  DROP CONSTRAINT IF EXISTS clutch_instances_cx_shape,
  ADD  CONSTRAINT clutch_instances_cx_shape
  CHECK (clutch_code ~ '^CX\([A-Z0-9-]+\)\([0-9]{2,}\)$');

-- Dedicated unique indexes
CREATE UNIQUE INDEX IF NOT EXISTS uq_cross_instances_cx_code
  ON public.cross_instances (cross_code);

CREATE UNIQUE INDEX IF NOT EXISTS uq_clutch_instances_cx_code
  ON public.clutch_instances (clutch_code);

COMMIT;

-- 4) Backfill existing rows

-- 4a) Backfill cross_instances.cross_code by dense per-TP sequence (ordered by created_at)
WITH ranked AS (
  SELECT
    ci.id,
    tp.tank_pair_code,
    ROW_NUMBER() OVER (PARTITION BY ci.tank_pair_id ORDER BY ci.created_at, ci.id) AS rn
  FROM public.cross_instances ci
  JOIN public.tank_pairs tp ON tp.id = ci.tank_pair_id
)
UPDATE public.cross_instances ci
SET cross_code = format('CX(%s)(%s)', r.tank_pair_code, lpad(r.rn::text, 2, '0'))
FROM ranked r
WHERE ci.id = r.id
  AND (ci.cross_code IS NULL OR ci.cross_code !~ '^CX\([A-Z0-9-]+\)\([0-9]{2,}\)$');

-- 4b) Backfill clutch_instances.clutch_code from linked cross
UPDATE public.clutch_instances cl
SET    clutch_code = ci.cross_code
FROM   public.cross_instances ci
WHERE  cl.cross_instance_id = ci.id
  AND (cl.clutch_code IS NULL OR cl.clutch_code !~ '^CX\([A-Z0-9-]+\)\([0-9]{2,}\)$');

-- 4c) Backfill missing birthdays as cross_date+1 day (if any)
UPDATE public.clutch_instances cl
SET    birthday = ci.cross_date + INTERVAL '1 day'
FROM   public.cross_instances ci
WHERE  cl.cross_instance_id = ci.id
  AND  cl.birthday IS NULL;

COMMIT;

