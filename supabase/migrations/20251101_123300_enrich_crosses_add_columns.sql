BEGIN;

-- Add the columns your page expects (skip if already present)
ALTER TABLE public.crosses
  ADD COLUMN IF NOT EXISTS tank_pair_code   text,
  ADD COLUMN IF NOT EXISTS cross_date       date,
  ADD COLUMN IF NOT EXISTS created_by       text,
  ADD COLUMN IF NOT EXISTS note             text,
  ADD COLUMN IF NOT EXISTS created_at       timestamptz DEFAULT now(),
  ADD COLUMN IF NOT EXISTS cross_run_code   text;

-- FK to tank_pairs (if not present)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.table_constraints
    WHERE table_schema='public' AND table_name='crosses' AND constraint_name='fk_crosses_tank_pair'
  ) THEN
    ALTER TABLE public.crosses
      ADD CONSTRAINT fk_crosses_tank_pair
      FOREIGN KEY (tank_pair_code) REFERENCES public.tank_pairs(tank_pair_code)
      ON UPDATE CASCADE ON DELETE RESTRICT;
  END IF;
END $$;

-- Unique run code + generator/trigger (CR-000001 style)
CREATE UNIQUE INDEX IF NOT EXISTS uq_crosses_run_code ON public.crosses(cross_run_code);
CREATE SEQUENCE IF NOT EXISTS public.seq_cross_run_code;

CREATE OR REPLACE FUNCTION public.next_cross_run_code()
RETURNS text
LANGUAGE plpgsql AS $$
DECLARE v text;
BEGIN
  LOOP
    v := 'CR-' || lpad(nextval('public.seq_cross_run_code')::text, 6, '0');
    EXIT WHEN NOT EXISTS (SELECT 1 FROM public.crosses WHERE cross_run_code = v);
  END LOOP;
  RETURN v;
END; $$;

CREATE OR REPLACE FUNCTION public.ensure_cross_run_code()
RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.cross_run_code IS NULL OR NEW.cross_run_code = '' THEN
    NEW.cross_run_code := public.next_cross_run_code();
  END IF;
  IF NEW.created_at IS NULL THEN
    NEW.created_at := now();
  END IF;
  RETURN NEW;
END; $$;

DROP TRIGGER IF EXISTS trg_crosses_run_code ON public.crosses;
CREATE TRIGGER trg_crosses_run_code
BEFORE INSERT ON public.crosses
FOR EACH ROW
EXECUTE FUNCTION public.ensure_cross_run_code();

COMMIT;
