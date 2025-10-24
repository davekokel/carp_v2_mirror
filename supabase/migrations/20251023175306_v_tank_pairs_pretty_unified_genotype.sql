BEGIN;

-- Snapshot-aware tank pairs with unified genotype for UI
CREATE OR REPLACE VIEW public.v_tank_pairs_pretty AS
SELECT
  tp.id,
  tp.tank_pair_code,
  tp.tp_seq,
  tp.status,
  tp.role_orientation,
  tp.created_by,
  tp.created_at,

  -- snapshot fields already on tank_pairs
  tp.mom_tank_code,
  tp.dad_tank_code,
  tp.mom_genotype,
  tp.dad_genotype,

  -- current fish codes from tanks
  mt.fish_code AS mom_fish_code,
  dt.fish_code AS dad_fish_code,

  -- most recent conceptual clutch linked to this pair (if any)
  cl.clutch_code,

  -- unified genotype: clutch → pair → snapshot fallback
  COALESCE(
    public._norm_genotype(cl.expected_genotype),
    public._norm_genotype(fp.pair_genotype),
    public._norm_genotype(
      CASE
        WHEN NULLIF(tp.mom_genotype,'') IS NOT NULL
         AND NULLIF(tp.dad_genotype,'') IS NOT NULL
        THEN tp.mom_genotype || ' × ' || tp.dad_genotype
        ELSE NULLIF(tp.mom_genotype,'')
      END
    )
  ) AS genotype

FROM public.tank_pairs tp
LEFT JOIN public.tanks      mt ON mt.tank_id = tp.mother_tank_id
LEFT JOIN public.tanks      dt ON dt.tank_id = tp.father_tank_id
LEFT JOIN public.fish_pairs fp ON fp.fish_pair_id = tp.fish_pair_id
LEFT JOIN LATERAL (
  SELECT c1.clutch_code, c1.expected_genotype, c1.created_at
  FROM public.clutches c1
  WHERE c1.fish_pair_id = tp.fish_pair_id
  ORDER BY c1.created_at DESC NULLS LAST
  LIMIT 1
) cl ON TRUE
ORDER BY tp.created_at DESC NULLS LAST;

COMMENT ON VIEW public.v_tank_pairs_pretty IS
  'Tank pairs with a single unified genotype column (clutch → pair → snapshot fallback) for UI tables.';

COMMIT;
