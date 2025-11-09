BEGIN;

-- 1) a tiny sequence for human-friendly codes
CREATE SEQUENCE IF NOT EXISTS public.seq_tank_pair_code;

-- 2) generator function: TP-YYYYMMDD-000001
CREATE OR REPLACE FUNCTION public.tank_pair_code_next()
RETURNS text
LANGUAGE sql
AS $$
  SELECT 'TP-'||to_char(now(),'YYYYMMDD')||'-'||lpad(nextval('public.seq_tank_pair_code')::text, 6, '0');
$$;

-- 3) trigger to assign the code on INSERT if it's null
CREATE OR REPLACE FUNCTION public.tank_pairs_bi_assign_code()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  IF NEW.tank_pair_code IS NULL OR NEW.tank_pair_code = '' THEN
    NEW.tank_pair_code := public.tank_pair_code_next();
  END IF;
  RETURN NEW;
END
$$;

DROP TRIGGER IF EXISTS trg_tank_pairs_bi_assign_code ON public.tank_pairs;
CREATE TRIGGER trg_tank_pairs_bi_assign_code
BEFORE INSERT ON public.tank_pairs
FOR EACH ROW
EXECUTE FUNCTION public.tank_pairs_bi_assign_code();

-- 4) optional: backfill any existing nulls now
UPDATE public.tank_pairs
SET tank_pair_code = public.tank_pair_code_next()
WHERE tank_pair_code IS NULL OR tank_pair_code='';

-- 5) optional: keep it unique & non-null if not already enforced
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid = 'public.tank_pairs'::regclass AND conname = 'uq_tank_pairs_code'
  ) THEN
    EXECUTE 'ALTER TABLE public.tank_pairs ADD CONSTRAINT uq_tank_pairs_code UNIQUE (tank_pair_code)';
  END IF;
EXCEPTION WHEN duplicate_table THEN
  -- ignore
END$$;

COMMIT;
