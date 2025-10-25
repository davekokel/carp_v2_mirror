BEGIN;

-- 1) Guard: do not proceed if any DB views depend on public.v_tank_pairs
DO $$
DECLARE
  deps int;
BEGIN
  SELECT count(*) INTO deps
  FROM information_schema.view_table_usage
  WHERE view_schema='public' AND table_schema='public' AND table_name='v_tank_pairs';

  IF deps > 0 THEN
    RAISE EXCEPTION 'Refusing to rebuild public.v_tank_pairs: % dependent DB view(s) detected. Update those dependents first (or use v_tank_pairs_v2).', deps;
  END IF;
END$$;

-- 2) Drop and recreate with explicit column list (so we can add new columns)
DROP VIEW IF EXISTS public.v_tank_pairs;

CREATE VIEW public.v_tank_pairs
( id,
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
  dad_genotype,
  tp_seq,
  pair_fish,
  pair_tanks,
  pair_genotype,
  genotype,
  clutch_code
) AS
WITH latest_clutch AS (
  SELECT
    c.fish_pair_id,
    c.clutch_code,
    c.expected_genotype,
    c.created_at,
    ROW_NUMBER() OVER (PARTITION BY c.fish_pair_id ORDER BY c.created_at DESC NULLS LAST) AS rn
  FROM public.clutches c
)
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
  mt.tank_id,
  COALESCE(tp.mom_tank_code, mt.tank_code),
  mt.fish_code,
  tp.mom_genotype,
  dt.tank_id,
  COALESCE(tp.dad_tank_code, dt.tank_code),
  dt.fish_code,
  tp.dad_genotype,
  tp.tp_seq,
  (COALESCE(mt.fish_code,'') || ' × ' || COALESCE(dt.fish_code,'')) AS pair_fish,
  (COALESCE(mt.tank_code,'') || ' × ' || COALESCE(dt.tank_code,'')) AS pair_tanks,
  CASE
    WHEN NULLIF(lc.expected_genotype,'') IS NOT NULL
      THEN lc.expected_genotype
    WHEN NULLIF(tp.mom_genotype,'') IS NOT NULL
     AND NULLIF(tp.dad_genotype,'') IS NOT NULL
      THEN tp.mom_genotype || ' × ' || tp.dad_genotype
    ELSE NULLIF(tp.mom_genotype,'')
  END AS pair_genotype,
  CASE
    WHEN NULLIF(lc.expected_genotype,'') IS NOT NULL
      THEN lc.expected_genotype
    WHEN NULLIF(tp.mom_genotype,'') IS NOT NULL
     AND NULLIF(tp.dad_genotype,'') IS NOT NULL
      THEN tp.mom_genotype || ' × ' || tp.dad_genotype
    ELSE NULLIF(tp.mom_genotype,'')
  END AS genotype,
  lc.clutch_code
FROM public.tank_pairs tp
LEFT JOIN public.tanks mt ON mt.tank_id = tp.mother_tank_id
LEFT JOIN public.tanks dt ON dt.tank_id = tp.father_tank_id
LEFT JOIN latest_clutch lc
  ON lc.fish_pair_id = tp.fish_pair_id AND lc.rn = 1
ORDER BY tp.created_at DESC NULLS LAST;

COMMENT ON VIEW public.v_tank_pairs IS
  'Snapshot-aware tank pairs with pretty helpers (pair_fish, pair_tanks, genotype) and clutch_code.';

COMMIT;
