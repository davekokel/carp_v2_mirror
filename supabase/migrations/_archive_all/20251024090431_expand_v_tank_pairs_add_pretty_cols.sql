BEGIN;

-- Optional: if an old wrapper exists, drop it (the canonical view will include the pretty cols)
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.views
    WHERE table_schema='public' AND table_name='v_tank_pairs_pretty'
  ) THEN
    EXECUTE 'DROP VIEW public.v_tank_pairs_pretty';
  END IF;
END$$;

-- Key idea: CREATE OR REPLACE (no renames/removals), so dependents stay intact.
CREATE OR REPLACE VIEW public.v_tank_pairs AS
WITH lc AS (
  SELECT
    c.fish_pair_id,
    c.expected_genotype,
    c.clutch_code,
    ROW_NUMBER() OVER (PARTITION BY c.fish_pair_id ORDER BY c.created_at DESC NULLS LAST) AS rn
  FROM public.clutches c
)
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

  -- legacy snapshot columns
  mt.tank_id                                          AS mother_tank_id,
  COALESCE(tp.mom_tank_code, mt.tank_code)            AS mom_tank_code,
  mt.fish_code                                        AS mom_fish_code,
  tp.mom_genotype,

  dt.tank_id                                          AS father_tank_id,
  COALESCE(tp.dad_tank_code, dt.tank_code)            AS dad_tank_code,
  dt.fish_code                                        AS dad_fish_code,
  tp.dad_genotype,

  -- pretty helpers (new)
  (COALESCE(mt.fish_code,'') || ' × ' || COALESCE(dt.fish_code,''))                                AS pair_fish,
  (COALESCE(COALESCE(tp.mom_tank_code, mt.tank_code),'') || ' × ' ||
   COALESCE(COALESCE(tp.dad_tank_code, dt.tank_code),''))                                          AS pair_tanks,
  CASE
    WHEN COALESCE(tp.mom_genotype,'') <> '' AND COALESCE(tp.dad_genotype,'') <> ''
      THEN tp.mom_genotype || ' × ' || tp.dad_genotype
    WHEN COALESCE(tp.mom_genotype,'') <> '' THEN tp.mom_genotype
    ELSE NULL
  END                                                                                              AS pair_genotype,

  -- unified filter/sort field (clutch overrides snapshot)
  CASE
    WHEN COALESCE(lc.expected_genotype,'') <> '' THEN lc.expected_genotype
    WHEN COALESCE(tp.mom_genotype,'') <> '' AND COALESCE(tp.dad_genotype,'') <> ''
      THEN tp.mom_genotype || ' × ' || tp.dad_genotype
    WHEN COALESCE(tp.mom_genotype,'') <> '' THEN tp.mom_genotype
    ELSE NULL
  END                                                                                              AS genotype,

  lc.clutch_code

FROM public.tank_pairs tp
LEFT JOIN public.tanks mt ON mt.tank_id = tp.mother_tank_id
LEFT JOIN public.tanks dt ON dt.tank_id = tp.father_tank_id
LEFT JOIN lc              ON lc.fish_pair_id = tp.fish_pair_id AND lc.rn = 1
ORDER BY tp.created_at DESC NULLS LAST;

COMMENT ON VIEW public.v_tank_pairs IS
  'Snapshot-aware tank pairs (legacy columns preserved) + UI helpers: pair_fish, pair_tanks, pair_genotype, genotype, clutch_code.';

COMMIT;
