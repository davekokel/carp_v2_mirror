BEGIN;

-- Drop first so we can change the column list (CREATE OR REPLACE cannot change names/count)
-- If something depends on the view, remove or adjust that dependency first or use CASCADE.
DROP VIEW IF EXISTS public.v_tank_pairs;

-- Recreate with explicit column list, tanks-only, exposing snapshot fields
CREATE VIEW public.v_tank_pairs (
  id,
  tank_pair_code,
  status,
  role_orientation,
  concept_id,
  fish_pair_id,
  created_by,
  created_at,
  updated_at,

  mother_tank_id,
  mom_tank_code,
  mom_fish_code,
  mom_genotype,

  father_tank_id,
  dad_tank_code,
  dad_fish_code,
  dad_genotype
) AS
SELECT
  tp.id,
  tp.tank_pair_code,
  tp.status,
  tp.role_orientation,
  tp.concept_id,
  tp.fish_pair_id,
  tp.created_by,
  tp.created_at,
  tp.updated_at,

  mt.tank_id                                 AS mother_tank_id,
  COALESCE(tp.mom_tank_code, mt.tank_code)   AS mom_tank_code,
  mt.fish_code                               AS mom_fish_code,
  tp.mom_genotype                            AS mom_genotype,

  dt.tank_id                                 AS father_tank_id,
  COALESCE(tp.dad_tank_code, dt.tank_code)   AS dad_tank_code,
  dt.fish_code                               AS dad_fish_code,
  tp.dad_genotype                            AS dad_genotype
FROM public.tank_pairs tp
LEFT JOIN public.tanks mt ON mt.tank_id = tp.mother_tank_id
LEFT JOIN public.tanks dt ON dt.tank_id = tp.father_tank_id
ORDER BY tp.created_at DESC NULLS LAST;

COMMIT;
