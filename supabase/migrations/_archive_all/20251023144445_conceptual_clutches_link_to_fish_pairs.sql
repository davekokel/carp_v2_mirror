BEGIN;

-- Let conceptual clutches exist without cross_id (we link via fish_pair_id/code)
ALTER TABLE public.clutches
  ALTER COLUMN cross_id DROP NOT NULL;

-- Ensure clutch_code is a stable conceptual identifier
ALTER TABLE public.clutches
  ADD CONSTRAINT clutches_code_unique UNIQUE (clutch_code);

CREATE INDEX IF NOT EXISTS idx_clutches_code            ON public.clutches(clutch_code);
CREATE INDEX IF NOT EXISTS idx_clutches_fish_pair_id    ON public.clutches(fish_pair_id);
CREATE INDEX IF NOT EXISTS idx_clutches_fish_pair_code  ON public.clutches(fish_pair_code);

-- Ensure fish_pairs is present and unique per ordered mom/dad
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

CREATE INDEX IF NOT EXISTS idx_fish_pairs_mom        ON public.fish_pairs(mom_fish_code);
CREATE INDEX IF NOT EXISTS idx_fish_pairs_dad        ON public.fish_pairs(dad_fish_code);
CREATE INDEX IF NOT EXISTS idx_fish_pairs_created_at ON public.fish_pairs(created_at);
CREATE INDEX IF NOT EXISTS idx_fish_pairs_code       ON public.fish_pairs(fish_pair_code);

COMMIT;
