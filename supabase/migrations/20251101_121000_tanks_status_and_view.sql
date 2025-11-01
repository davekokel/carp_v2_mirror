BEGIN;

-- 1) Ensure status column on base table with constraint + default
ALTER TABLE public.tanks
  ADD COLUMN IF NOT EXISTS status text;

-- default 'active' for new rows
ALTER TABLE public.tanks
  ALTER COLUMN status SET DEFAULT 'active';

-- backfill any NULLs to 'active'
UPDATE public.tanks SET status = 'active' WHERE status IS NULL;

-- constrain allowed values
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid = 'public.tanks'::regclass AND conname = 'ck_tanks_status_allowed'
  ) THEN
    ALTER TABLE public.tanks
      ADD CONSTRAINT ck_tanks_status_allowed
      CHECK (status IN ('active','to_kill','retired'));
  END IF;
END $$;

-- 2) Helpful indexes
CREATE INDEX IF NOT EXISTS ix_tanks_fish_code ON public.tanks(fish_code);
CREATE INDEX IF NOT EXISTS ix_tanks_status    ON public.tanks(status);
CREATE INDEX IF NOT EXISTS ix_tanks_created   ON public.tanks(created_at);

-- 3) (Re)define v_tanks to include status + dependable fish_code
--    If fish_code column is NULL/missing in rows, derive it from tank_code: TANK(<code>)#N
CREATE OR REPLACE VIEW public.v_tanks AS
SELECT
  t.tank_uuid,
  t.tank_code,
  COALESCE(t.fish_code,
           regexp_replace(t.tank_code, '^.*\(([^)]+)\).*$', '\1')) AS fish_code,
  t.status,
  t.created_at
FROM public.tanks t;

COMMIT;
