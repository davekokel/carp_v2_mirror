BEGIN;

-- Ensure status column exists and has sane default/constraint
ALTER TABLE public.tanks
  ADD COLUMN IF NOT EXISTS status text;

ALTER TABLE public.tanks
  ALTER COLUMN status SET DEFAULT 'active';

UPDATE public.tanks
SET status = 'active'
WHERE status IS NULL;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid='public.tanks'::regclass AND conname='ck_tanks_status_allowed'
  ) THEN
    ALTER TABLE public.tanks
      ADD CONSTRAINT ck_tanks_status_allowed
      CHECK (status IN ('active','to_kill','retired'));
  END IF;
END $$;

-- Helpful indexes (NO index on tanks(fish_code) — that column does not exist)
CREATE INDEX IF NOT EXISTS ix_tanks_status  ON public.tanks(status);
CREATE INDEX IF NOT EXISTS ix_tanks_created ON public.tanks(created_at);

-- Adaptive v_tanks: expose (tank_uuid, tank_code, fish_code, status, created_at)
DROP VIEW IF EXISTS public.v_tanks;

DO $$
DECLARE
  has_tank_uuid boolean;
  has_id        boolean;
  has_status    boolean;
  has_created   boolean;
  key_col       text;
  created_col   text;
  sql_view      text;
BEGIN
  SELECT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='tanks' AND column_name='tank_uuid'
  ) INTO has_tank_uuid;

  SELECT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='tanks' AND column_name='id'
  ) INTO has_id;

  key_col := CASE WHEN has_tank_uuid THEN 'tank_uuid'
                  WHEN has_id       THEN 'id'
                  ELSE NULL END;
  IF key_col IS NULL THEN
    RAISE EXCEPTION 'public.tanks must have either tank_uuid or id';
  END IF;

  SELECT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='tanks' AND column_name='status'
  ) INTO has_status;

  SELECT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='tanks' AND column_name='created_at'
  ) INTO has_created;

  created_col := CASE WHEN has_created THEN 'created_at' ELSE 'now()' END;

  sql_view := format($v$
    CREATE VIEW public.v_tanks AS
    SELECT
      t.%I              AS tank_uuid,
      t.tank_code       AS tank_code,
      regexp_replace(t.tank_code, '^.*\(([^)]+)\).*$', '\1') AS fish_code,
      %s                AS status,
      %s::timestamptz   AS created_at
    FROM public.tanks t;
  $v$, key_col,
      CASE WHEN has_status THEN 't.status' ELSE '''''' END,
      created_col);

  EXECUTE sql_view;
END $$;

COMMIT;
