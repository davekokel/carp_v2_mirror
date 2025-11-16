BEGIN;

-- 0) Ensure the column exists before any references
ALTER TABLE public.tanks
  ADD COLUMN IF NOT EXISTS fish_id uuid;

-- 1) Backfill fish_id from tank_code -> fish.fish_code (only where still null)
WITH m AS (
  SELECT
    t.id AS tank_id,
    substring(t.tank_code from '\(([^)]+)\)') AS parsed_fish_code
  FROM public.tanks t
  WHERE t.fish_id IS NULL
)
UPDATE public.tanks t
SET    fish_id = f.id
FROM   m
JOIN   public.fish f ON f.fish_code = m.parsed_fish_code
WHERE  t.id = m.tank_id
  AND  t.fish_id IS NULL;

-- 2) FK and index (idempotent)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname='fk_tanks_fish' AND conrelid='public.tanks'::regclass
  ) THEN
    ALTER TABLE public.tanks
      ADD CONSTRAINT fk_tanks_fish
      FOREIGN KEY (fish_id) REFERENCES public.fish(id)
      ON UPDATE CASCADE ON DELETE RESTRICT;
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_class WHERE relname='ix_tanks_fish_id') THEN
    CREATE INDEX ix_tanks_fish_id ON public.tanks(fish_id);
  END IF;
END$$;

-- 3) Strict view (pure FK join; no parsing)
DROP VIEW IF EXISTS public.v_tanks_overview CASCADE;
CREATE VIEW public.v_tanks_overview AS
SELECT
  t.id::text                  AS id,
  t.tank_code::text           AS tank_code,
  f.fish_code::text           AS fish_code,
  COALESCE(t.status::text,'') AS status,
  t.created_at::timestamptz   AS created_at
FROM public.tanks t
JOIN public.fish f ON f.id = t.fish_id;

-- 4) Enforce NOT NULL if backfill succeeded fully
DO $$
DECLARE miss int;
BEGIN
  SELECT COUNT(*) INTO miss FROM public.tanks WHERE fish_id IS NULL;
  IF miss = 0 THEN
    BEGIN
      ALTER TABLE public.tanks ALTER COLUMN fish_id SET NOT NULL;
    EXCEPTION WHEN OTHERS THEN
      NULL;
    END;
  END IF;
END$$;

COMMIT;
