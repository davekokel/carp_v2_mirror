BEGIN;

-- v_tank_pairs_pretty: adds human-friendly composites on top of v_tank_pairs
CREATE OR REPLACE VIEW public.v_tank_pairs_pretty AS
SELECT
  tp.id,
  tp.tank_pair_code,
  tp.tp_seq,
  tp.status,
  tp.role_orientation,
  tp.concept_id,
  tp.fish_pair_id,
  tp.created_by,
  tp.created_at,
  tp.updated_at,

  -- canonical snapshot & ids
  tp.mother_tank_id,
  tp.mom_tank_code,
  tp.mom_fish_code,
  tp.mom_genotype,
  tp.father_tank_id,
  tp.dad_tank_code,
  tp.dad_fish_code,
  tp.dad_genotype,

  -- pretty composites
  (COALESCE(tp.mom_fish_code,'') || ' × ' || COALESCE(tp.dad_fish_code,''))            AS pair_fish,
  (COALESCE(tp.mom_tank_code,'') || ' × ' || COALESCE(tp.dad_tank_code,''))            AS pair_tanks,
  CASE
    WHEN COALESCE(tp.mom_genotype,'') = '' AND COALESCE(tp.dad_genotype,'') = '' THEN ''
    WHEN COALESCE(tp.mom_genotype,'') = '' THEN tp.dad_genotype
    WHEN COALESCE(tp.dad_genotype,'') = '' THEN tp.mom_genotype
    ELSE tp.mom_genotype || ' × ' || tp.dad_genotype
  END                                                                                  AS pair_genotype
FROM public.v_tank_pairs tp
ORDER BY tp.created_at DESC NULLS LAST;

COMMENT ON VIEW public.v_tank_pairs_pretty
  IS 'Tank pairs with human-readable composites: pair_fish, pair_tanks, pair_genotype (derived from v_tank_pairs).';

COMMIT;
