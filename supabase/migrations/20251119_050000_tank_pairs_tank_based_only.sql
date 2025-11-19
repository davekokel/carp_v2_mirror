BEGIN;

-- 1. Ensure we have tank_pair_code
ALTER TABLE public.tank_pairs
ADD COLUMN IF NOT EXISTS tank_pair_code text;

-- 2. Drop old FKs and columns that encode fish-based or single-tank pairing

ALTER TABLE public.tank_pairs
DROP CONSTRAINT IF EXISTS tank_pairs_tank_id_fkey,
DROP CONSTRAINT IF EXISTS tank_pairs_female_fish_id_fkey,
DROP CONSTRAINT IF EXISTS tank_pairs_male_fish_id_fkey;

ALTER TABLE public.tank_pairs
DROP COLUMN IF EXISTS tank_id,
DROP COLUMN IF EXISTS female_fish_id,
DROP COLUMN IF EXISTS male_fish_id;

-- 3. Make mother_tank_id / father_tank_id required and tighten FKs

ALTER TABLE public.tank_pairs
ALTER COLUMN mother_tank_id SET NOT NULL,
ALTER COLUMN father_tank_id SET NOT NULL;

ALTER TABLE public.tank_pairs
DROP CONSTRAINT IF EXISTS fk_tank_pairs_mother_tank,
DROP CONSTRAINT IF EXISTS fk_tank_pairs_father_tank;

ALTER TABLE public.tank_pairs
ADD CONSTRAINT fk_tank_pairs_mother_tank
  FOREIGN KEY (mother_tank_id) REFERENCES public.tanks(id)
  ON UPDATE CASCADE ON DELETE RESTRICT;

ALTER TABLE public.tank_pairs
ADD CONSTRAINT fk_tank_pairs_father_tank
  FOREIGN KEY (father_tank_id) REFERENCES public.tanks(id)
  ON UPDATE CASCADE ON DELETE RESTRICT;

-- 4. Optional: make tank_pair_code unique and non-null going forward

ALTER TABLE public.tank_pairs
ALTER COLUMN tank_pair_code SET NOT NULL;

ALTER TABLE public.tank_pairs
ADD CONSTRAINT uq_tank_pairs_code UNIQUE (tank_pair_code);

COMMIT;
