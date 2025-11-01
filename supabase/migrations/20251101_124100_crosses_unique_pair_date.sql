BEGIN;

-- Ensure the columns exist (no-ops if they already do)
ALTER TABLE public.crosses
  ADD COLUMN IF NOT EXISTS tank_pair_code text,
  ADD COLUMN IF NOT EXISTS cross_date     date,
  ADD COLUMN IF NOT EXISTS created_by     text,
  ADD COLUMN IF NOT EXISTS note           text,
  ADD COLUMN IF NOT EXISTS created_at     timestamptz DEFAULT now(),
  ADD COLUMN IF NOT EXISTS cross_run_code text;

-- Optional FK to tank_pairs if not present yet
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM information_schema.table_constraints
    WHERE table_schema='public' AND table_name='crosses' AND constraint_name='fk_crosses_tank_pair'
  ) THEN
    ALTER TABLE public.crosses
      ADD CONSTRAINT fk_crosses_tank_pair
      FOREIGN KEY (tank_pair_code) REFERENCES public.tank_pairs(tank_pair_code)
      ON UPDATE CASCADE ON DELETE RESTRICT;
  END IF;
END $$;

-- De-duplicate by (tank_pair_code, cross_date): keep the most recent row
WITH dups AS (
  SELECT
    id,
    row_number() OVER (
      PARTITION BY tank_pair_code, cross_date
      ORDER BY created_at DESC NULLS LAST, id DESC
    ) AS rn
  FROM public.crosses
  WHERE tank_pair_code IS NOT NULL AND cross_date IS NOT NULL
),
del AS (
  DELETE FROM public.crosses c
  USING dups d
  WHERE c.id = d.id AND d.rn > 1
  RETURNING 1
)
SELECT COALESCE((SELECT count(*) FROM del), 0) AS removed_dupes;

-- Add the actual UNIQUE constraint used by ON CONFLICT
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM information_schema.table_constraints
    WHERE table_schema='public'
      AND table_name='crosses'
      AND constraint_type='UNIQUE'
      AND constraint_name='uq_crosses_pair_date'
  ) THEN
    ALTER TABLE public.crosses
      ADD CONSTRAINT uq_crosses_pair_date UNIQUE (tank_pair_code, cross_date);
  END IF;
END $$;

COMMIT;
