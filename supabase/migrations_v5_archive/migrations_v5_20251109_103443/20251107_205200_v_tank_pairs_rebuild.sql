BEGIN;

-- Replace the view so it always exposes the fields your page expects
DROP VIEW IF EXISTS public.v_tank_pairs;

CREATE VIEW public.v_tank_pairs AS
SELECT
  tp.tank_pair_code,
  -- Mother info
  vtm.fish_code                      AS mom_fish_code,
  vtm.tank_code                      AS mom_tank_code,
  vfm.genotype_pretty                AS mom_genotype,
  -- Father info
  vtf.fish_code                      AS dad_fish_code,
  vtf.tank_code                      AS dad_tank_code,
  vff.genotype_pretty                AS dad_genotype,
  -- Combined strings for convenience
  (COALESCE(vtm.fish_code,'') || ' × ' || COALESCE(vtf.fish_code,'')) AS fish_pair_code,
  (COALESCE(vtm.tank_code,'') || ' × ' || COALESCE(vtf.tank_code,'')) AS pair_tanks,
  -- Timestamps
  tp.created_at
FROM public.tank_pairs tp
LEFT JOIN public.v_tanks vtm
  ON vtm.tank_uuid = tp.mother_tank_id
LEFT JOIN public.v_tanks vtf
  ON vtf.tank_uuid = tp.father_tank_id
LEFT JOIN public.v_fish_unified vfm
  ON vfm.fish_code = vtm.fish_code
LEFT JOIN public.v_fish_unified vff
  ON vff.fish_code = vtf.fish_code;

COMMIT;
