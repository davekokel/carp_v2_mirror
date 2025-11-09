BEGIN;

-- 1) Ensure table exists with the columns we actually use
CREATE TABLE IF NOT EXISTS public.tanks (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tank_code  text NOT NULL,
  status     text,
  created_at timestamptz NOT NULL DEFAULT now()
);

-- 2) Add status if missing (idempotent)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='tanks' AND column_name='status'
  ) THEN
    ALTER TABLE public.tanks ADD COLUMN status text;
  END IF;
END$$;

-- 3) Unique index on tank_code (idempotent)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_indexes
    WHERE schemaname='public' AND tablename='tanks' AND indexname='uq_tanks_tank_code'
  ) THEN
    CREATE UNIQUE INDEX uq_tanks_tank_code ON public.tanks(tank_code);
  END IF;
END$$;

-- 4) Basic before-insert defaults (idempotent)
CREATE OR REPLACE FUNCTION public.tanks_bi_set_defaults()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.created_at IS NULL THEN NEW.created_at := now(); END IF;
  RETURN NEW;
END
$$;

DROP TRIGGER IF EXISTS trg_tanks_bi_set_defaults ON public.tanks;
CREATE TRIGGER trg_tanks_bi_set_defaults
BEFORE INSERT ON public.tanks
FOR EACH ROW EXECUTE FUNCTION public.tanks_bi_set_defaults();

-- 5) Recreate v_tanks to match the real table columns.
--    id → tank_uuid; derive fish_code & tank_num from tank_code "TANK(<fish_code>)#<n>"
DROP VIEW IF EXISTS public.v_tanks;
CREATE VIEW public.v_tanks AS
SELECT
  t.id::uuid AS tank_uuid,
  t.tank_code::text AS tank_code,
  COALESCE(
    NULLIF(regexp_replace(t.tank_code, '^.*\(([^)]+)\).*$', '\1'), ''),
    ''
  )::text AS fish_code,
  NULLIF(regexp_replace(t.tank_code, '^.*#([0-9]+).*$', '\1'), '')::int AS tank_num,
  t.status::text AS status,
  t.created_at
FROM public.tanks t
ORDER BY t.created_at DESC NULLS LAST, t.tank_code;

COMMIT;
