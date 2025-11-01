BEGIN;

-- 1) Sequence for human-friendly codes (monotonic)
CREATE SEQUENCE IF NOT EXISTS public.seq_tank_pair_code;

-- 2) Unique index on the code
CREATE UNIQUE INDEX IF NOT EXISTS uq_tank_pairs_code
  ON public.tank_pairs(tank_pair_code);

-- 3) Generator: TP-000001 style, loop guards against the (unlikely) race
CREATE OR REPLACE FUNCTION public.next_tank_pair_code()
RETURNS text
LANGUAGE plpgsql
AS $$
DECLARE
  v text;
BEGIN
  LOOP
    v := 'TP-' || lpad(nextval('public.seq_tank_pair_code')::text, 6, '0');
    EXIT WHEN NOT EXISTS (
      SELECT 1 FROM public.tank_pairs WHERE tank_pair_code = v
    );
  END LOOP;
  RETURN v;
END;
$$;

-- 4) Trigger to assign the code on INSERT when missing
CREATE OR REPLACE FUNCTION public.ensure_tank_pair_code()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  IF NEW.tank_pair_code IS NULL OR NEW.tank_pair_code = '' THEN
    NEW.tank_pair_code := public.next_tank_pair_code();
  END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_tank_pairs_code ON public.tank_pairs;
CREATE TRIGGER trg_tank_pairs_code
BEFORE INSERT ON public.tank_pairs
FOR EACH ROW
EXECUTE FUNCTION public.ensure_tank_pair_code();

-- 5) Backfill any existing NULLs (if present)
UPDATE public.tank_pairs
SET tank_pair_code = public.next_tank_pair_code()
WHERE tank_pair_code IS NULL;

COMMIT;
