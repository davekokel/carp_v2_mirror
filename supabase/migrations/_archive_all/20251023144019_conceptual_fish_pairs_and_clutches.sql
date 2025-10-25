BEGIN;

-- ---------------------------------------------------------------------------
-- Prereqs
-- ---------------------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ---------------------------------------------------------------------------
-- fish_pairs: clean schema (idempotent)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.fish_pairs (
  fish_pair_id   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  fish_pair_code text UNIQUE,
  mom_fish_code  text NOT NULL,
  dad_fish_code  text NOT NULL,
  genotype_elems text[] NULL,
  created_by     text NULL,
  created_at     timestamptz NOT NULL DEFAULT now(),
  CHECK (mom_fish_code <> dad_fish_code)
);

-- Uniqueness on ordered conceptual pair (Mom, Dad)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
     WHERE conname='fish_pairs_mom_dad_unique'
       AND conrelid='public.fish_pairs'::regclass
  ) THEN
    ALTER TABLE public.fish_pairs
      ADD CONSTRAINT fish_pairs_mom_dad_unique
      UNIQUE (mom_fish_code, dad_fish_code);
  END IF;
END$$;

-- Helpful indexes
CREATE INDEX IF NOT EXISTS idx_fish_pairs_mom        ON public.fish_pairs(mom_fish_code);
CREATE INDEX IF NOT EXISTS idx_fish_pairs_dad        ON public.fish_pairs(dad_fish_code);
CREATE INDEX IF NOT EXISTS idx_fish_pairs_created_at ON public.fish_pairs(created_at);
CREATE INDEX IF NOT EXISTS idx_fish_pairs_code       ON public.fish_pairs(fish_pair_code);

-- ---------------------------------------------------------------------------
-- Backfill fish_pair_code for any NULL codes as FP-YYNNNN (stable, monotonic)
-- ---------------------------------------------------------------------------
WITH to_fill AS (
  SELECT fish_pair_id
  FROM public.fish_pairs
  WHERE fish_pair_code IS NULL
  ORDER BY created_at, fish_pair_id
),
seq AS (
  SELECT fish_pair_id, ROW_NUMBER() OVER (ORDER BY fish_pair_id) AS rn
  FROM to_fill
),
maxn AS (
  SELECT
    COALESCE(MAX((regexp_match(COALESCE(fish_pair_code,''), '^FP-\d{2}(\d{4})$'))[1]::int), 0) AS n,
    to_char(extract(YEAR FROM now())::int % 100, 'FM00')                                      AS yy
  FROM public.fish_pairs
)
UPDATE public.fish_pairs f
SET fish_pair_code = 'FP-'||(SELECT yy FROM maxn)||LPAD(((SELECT n FROM maxn)+s.rn)::text, 4, '0')
FROM seq s
WHERE f.fish_pair_id = s.fish_pair_id
  AND f.fish_pair_code IS NULL;

-- ---------------------------------------------------------------------------
-- clutches: explicit conceptual link to fish_pairs (idempotent)
-- ---------------------------------------------------------------------------
ALTER TABLE public.clutches
  ADD COLUMN IF NOT EXISTS fish_pair_id   uuid,
  ADD COLUMN IF NOT EXISTS fish_pair_code text;

-- Helpful indexes for the link
CREATE INDEX IF NOT EXISTS idx_clutches_fish_pair_id   ON public.clutches(fish_pair_id);
CREATE INDEX IF NOT EXISTS idx_clutches_fish_pair_code ON public.clutches(fish_pair_code);

-- (Optional but recommended) Indexes that make conceptual lookups fast
-- CREATE INDEX IF NOT EXISTS idx_tc_mom_dad_created   ON public.tank_crosses(mom_fish_code, dad_fish_code, created_at);
-- CREATE INDEX IF NOT EXISTS idx_clutches_cross_created ON public.clutches(cross_id, created_at);

COMMIT;
