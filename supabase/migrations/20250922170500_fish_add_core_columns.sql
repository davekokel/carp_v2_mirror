BEGIN;

-- Add the columns the seedkit expects (safe if they already exist)
ALTER TABLE public.fish
  ADD COLUMN IF NOT EXISTS date_of_birth       date,
  ADD COLUMN IF NOT EXISTS line_building_stage text,
  ADD COLUMN IF NOT EXISTS strain              text;

-- Ensure fish_code exists & is unique
ALTER TABLE public.fish
  ADD COLUMN IF NOT EXISTS fish_code text;

CREATE UNIQUE INDEX IF NOT EXISTS fish_fish_code_key
  ON public.fish(fish_code);

-- Keep these handy on genetics tables
ALTER TABLE public.transgenes
  ADD COLUMN IF NOT EXISTS name        text,
  ADD COLUMN IF NOT EXISTS description text;

ALTER TABLE public.transgene_alleles
  ADD COLUMN IF NOT EXISTS description text;

COMMIT;
