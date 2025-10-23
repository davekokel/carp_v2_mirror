BEGIN;

-- 1) public.clutches.cross_id: drop NOT NULL only if currently NOT NULL
DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema='public' AND table_name='clutches'
      AND column_name='cross_id' AND is_nullable='NO'
  ) THEN
    EXECUTE 'ALTER TABLE public.clutches ALTER COLUMN cross_id DROP NOT NULL';
  END IF;
END$$;

-- 2) Ensure clutch_code is a unique conceptual identifier
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname='clutches_code_unique'
      AND conrelid='public.clutches'::regclass
  ) THEN
    ALTER TABLE public.clutches
      ADD CONSTRAINT clutches_code_unique UNIQUE (clutch_code);
  END IF;
END$$;

-- 3) Link columns for conceptual clutches → fish_pairs (idempotent)
ALTER TABLE public.clutches
  ADD COLUMN IF NOT EXISTS fish_pair_id   uuid,
  ADD COLUMN IF NOT EXISTS fish_pair_code text;

-- Helpful indexes (idempotent)
CREATE INDEX IF NOT EXISTS idx_clutches_code            ON public.clutches(clutch_code);
CREATE INDEX IF NOT EXISTS idx_clutches_fish_pair_id    ON public.clutches(fish_pair_id);
CREATE INDEX IF NOT EXISTS idx_clutches_fish_pair_code  ON public.clutches(fish_pair_code);

-- 4) Ensure public.fish_pairs canonical schema is present
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
    SELECT 1
    FROM pg_constraint
    WHERE conname='fish_pairs_mom_dad_unique'
      AND conrelid='public.fish_pairs'::regclass
  ) THEN
    ALTER TABLE public.fish_pairs
      ADD CONSTRAINT fish_pairs_mom_dad_unique
      UNIQUE (mom_fish_code, dad_fish_code);
  END IF;
END$$;

-- Helpful indexes for fish_pairs
CREATE INDEX IF NOT EXISTS idx_fish_pairs_mom        ON public.fish_pairs(mom_fish_code);
CREATE INDEX IF NOT EXISTS idx_fish_pairs_dad        ON public.fish_pairs(dad_fish_code);
CREATE INDEX IF NOT EXISTS idx_fish_pairs_created_at ON public.fish_pairs(created_at);
CREATE INDEX IF NOT EXISTS idx_fish_pairs_code       ON public.fish_pairs(fish_pair_code);

COMMIT;
