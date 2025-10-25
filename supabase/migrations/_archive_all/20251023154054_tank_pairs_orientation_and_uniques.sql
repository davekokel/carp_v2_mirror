BEGIN;

-- 1) Add a small role/orientation flag for physical pairings:
--    0 = mother_tank_id as chosen mother, 1 = flipped (father becomes mother)
ALTER TABLE public.tank_pairs
  ADD COLUMN IF NOT EXISTS role_orientation smallint NOT NULL DEFAULT 0;

-- 2) Normalize concept_id when absent so we can upsert with ON CONFLICT.
--    (We won't change the column default here; we'll pass a sentinel from app code.)

-- 3) Unique index per "roleful" row (allows both orientations by making them distinct):
--    Use a sentinel UUID to unify NULL concept_id (must match the app code).
CREATE UNIQUE INDEX IF NOT EXISTS tank_pairs_roleful_uq
ON public.tank_pairs (
  COALESCE(concept_id, '00000000-0000-0000-0000-000000000000'::uuid),
  mother_tank_id,
  father_tank_id,
  role_orientation
);

COMMENT ON COLUMN public.tank_pairs.role_orientation
  IS '0=as selected (mother_tank_id, father_tank_id); 1=flipped orientation';

COMMIT;
