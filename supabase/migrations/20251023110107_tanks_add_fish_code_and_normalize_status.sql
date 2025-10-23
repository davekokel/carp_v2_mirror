BEGIN;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM pg_type t
    JOIN pg_enum e ON e.enumtypid = t.oid
    WHERE t.typname = 'tank_status' AND e.enumlabel = 'new_tank'
  ) AND NOT EXISTS (
    SELECT 1
    FROM pg_type t
    JOIN pg_enum e ON e.enumtypid = t.oid
    WHERE t.typname = 'tank_status' AND e.enumlabel = 'new'
  ) THEN
    ALTER TYPE tank_status RENAME VALUE 'new_tank' TO 'new';
  END IF;
END$$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_type t JOIN pg_enum e ON e.enumtypid=t.oid
    WHERE t.typname='tank_status' AND e.enumlabel='active'
  ) THEN ALTER TYPE tank_status ADD VALUE 'active'; END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_type t JOIN pg_enum e ON e.enumtypid=t.oid
    WHERE t.typname='tank_status' AND e.enumlabel='to_kill'
  ) THEN ALTER TYPE tank_status ADD VALUE 'to_kill'; END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_type t JOIN pg_enum e ON e.enumtypid=t.oid
    WHERE t.typname='tank_status' AND e.enumlabel='retired'
  ) THEN ALTER TYPE tank_status ADD VALUE 'retired'; END IF;
END$$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='tanks' AND column_name='fish_code'
  ) THEN
    ALTER TABLE public.tanks ADD COLUMN fish_code text;
    ALTER TABLE public.tanks ADD CONSTRAINT tanks_fish_code_fkey
      FOREIGN KEY (fish_code) REFERENCES public.fish(fish_code);
    CREATE INDEX IF NOT EXISTS idx_tanks_fish_code ON public.tanks(fish_code);
  END IF;
END$$;

CREATE OR REPLACE VIEW public.v_tanks
( tank_id, label, tank_code, status, tank_updated_at, tank_created_at, fish_code ) AS
WITH last_status AS (
  SELECT s.tank_id, s.status, s.changed_at,
         row_number() OVER (PARTITION BY s.tank_id ORDER BY s.changed_at DESC) rn
  FROM tank_status_history s
)
SELECT
  t.tank_id,
  t.tank_code AS label,
  t.tank_code AS tank_code,
  ls.status,
  ls.changed_at AS tank_updated_at,
  t.created_at AS tank_created_at,
  t.fish_code
FROM tanks t
LEFT JOIN last_status ls ON ls.tank_id = t.tank_id AND ls.rn = 1;

COMMIT;
