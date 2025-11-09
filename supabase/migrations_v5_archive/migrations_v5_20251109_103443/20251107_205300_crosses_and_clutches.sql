BEGIN;

-- =========================
-- CROSSES
-- =========================
CREATE TABLE IF NOT EXISTS public.crosses (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tank_pair_code   text NOT NULL,
  cross_date       date NOT NULL,
  cross_run_code   text NOT NULL,                -- your page reads this
  created_by       text,
  note             text,
  created_at       timestamptz NOT NULL DEFAULT now()
);

-- idempotent unique key used by your page's ON CONFLICT clause
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_indexes
    WHERE schemaname='public' AND indexname='uq_crosses_pair_date'
  ) THEN
    EXECUTE 'CREATE UNIQUE INDEX uq_crosses_pair_date ON public.crosses(tank_pair_code, cross_date)';
  END IF;
END$$;

-- sequence + function to generate cross_run_code like CR-YYYYMMDD-000001
CREATE SEQUENCE IF NOT EXISTS public.seq_cross_run_code;

CREATE OR REPLACE FUNCTION public.cross_run_code_next()
RETURNS text
LANGUAGE sql
AS $$
  SELECT 'CR-'||to_char(now(),'YYYYMMDD')||'-'||lpad(nextval('public.seq_cross_run_code')::text, 6, '0');
$$;

CREATE OR REPLACE FUNCTION public.crosses_bi_assign_code()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  IF NEW.cross_run_code IS NULL OR NEW.cross_run_code = '' THEN
    NEW.cross_run_code := public.cross_run_code_next();
  END IF;
  RETURN NEW;
END
$$;

DROP TRIGGER IF EXISTS trg_crosses_bi_assign_code ON public.crosses;
CREATE TRIGGER trg_crosses_bi_assign_code
BEFORE INSERT ON public.crosses
FOR EACH ROW
EXECUTE FUNCTION public.crosses_bi_assign_code();

-- =========================
-- CLUTCH INSTANCES
-- =========================
CREATE TABLE IF NOT EXISTS public.clutch_instances (
  id                       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  cross_instance_id        uuid NOT NULL REFERENCES public.crosses(id) ON DELETE CASCADE,
  tank_pair_code           text NOT NULL,                      -- your page inserts this
  clutch_instance_code     text NOT NULL,
  clutch_genotype_pretty   text NOT NULL,                      -- your page inserts this
  normalized_genotype      text NOT NULL,                      -- used by ON CONFLICT
  created_at               timestamptz NOT NULL DEFAULT now()
);

-- uniqueness your page depends on:
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_indexes
    WHERE schemaname='public' AND indexname='uq_clutches_cross_normgeno'
  ) THEN
    EXECUTE 'CREATE UNIQUE INDEX uq_clutches_cross_normgeno
             ON public.clutch_instances(cross_instance_id, normalized_genotype)';
  END IF;
END$$;

-- clutch code generator: CI-YYYYMMDD-000001
CREATE SEQUENCE IF NOT EXISTS public.seq_clutch_instance_code;

CREATE OR REPLACE FUNCTION public.clutch_instance_code_next()
RETURNS text
LANGUAGE sql
AS $$
  SELECT 'CI-'||to_char(now(),'YYYYMMDD')||'-'||lpad(nextval('public.seq_clutch_instance_code')::text, 6, '0');
$$;

-- simple normalizer: lowercase and collapse non-alphanumerics to a single hyphen
CREATE OR REPLACE FUNCTION public.normalize_genotype(p text)
RETURNS text
LANGUAGE sql
AS $$
  SELECT regexp_replace(lower(coalesce(p,'')), '[^a-z0-9]+', '-', 'g');
$$;

CREATE OR REPLACE FUNCTION public.clutch_instances_bi_assign_fields()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  IF NEW.clutch_instance_code IS NULL OR NEW.clutch_instance_code = '' THEN
    NEW.clutch_instance_code := public.clutch_instance_code_next();
  END IF;
  NEW.normalized_genotype := public.normalize_genotype(NEW.clutch_genotype_pretty);
  RETURN NEW;
END
$$;

DROP TRIGGER IF EXISTS trg_clutch_instances_bi_assign_fields ON public.clutch_instances;
CREATE TRIGGER trg_clutch_instances_bi_assign_fields
BEFORE INSERT ON public.clutch_instances
FOR EACH ROW
EXECUTE FUNCTION public.clutch_instances_bi_assign_fields();

COMMIT;
