BEGIN;

-- Rebuild v_tank_pairs with an explicit output column list to avoid accidental renames.
-- Ordered to match the current view (through tp_seq), then append new columns.

CREATE OR REPLACE VIEW public.v_tank_pairs
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
  tp_seq,             -- existing column; keep position
  pair_fish,          -- NEW pretty helpers start here
  pair_tanks,         -- NEW
  pair_genotype,      -- NEW
  genotype,           -- NEW (stable alias of pair_genotype for search/UI)
  clutch_code         -- NEW (latest conceptual clutch for this fish_pair)
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

  mt.tank_id                                                  AS mother_tank_id,
  COALESCE(tp.mom_tank_code, mt.tank_code)                    AS mom_tank_code,
  mt.fish_code                                                AS mom_fish_code,
  tp.mom_genotype                                             AS mom_genotype,

  dt.tank_id                                                  AS father_tank_id,
  COALESCE(tp.dad_tank_code, dt.tank_code)                    AS dad_tank_code,
  dt.fish_code                                                AS dad_fish_code,
  tp.dad_genotype                                             AS dad_genotype,

  tp.tp_seq,

  -- Pretty helpers
  (COALESCE(mt.fish_code,'') || ' × ' || COALESCE(dt.fish_code,''))  AS pair_fish,
  (COALESCE(mt.tank_code,'') || ' × ' || COALESCE(dt.tank_code,''))  AS pair_tanks,

  CASE
    WHEN NULLIF(lc.expected_genotype,'') IS NOT NULL
      THEN lc.expected_genotype
    WHEN NULLIF(tp.mom_genotype,'') IS NOT NULL
     AND NULLIF(tp.dad_genotype,'') IS NOT NULL
      THEN tp.mom_genotype || ' × ' || tp.dad_genotype
    ELSE NULLIF(tp.mom_genotype,'')
  END                                                           AS pair_genotype,

  CASE
    WHEN NULLIF(lc.expected_genotype,'') IS NOT NULL
      THEN lc.expected_genotype
    WHEN NULLIF(tp.mom_genotype,'') IS NOT NULL
     AND NULLIF(tp.dad_genotype,'') IS NOT NULL
      THEN tp.mom_genotype || ' × ' || tp.dad_genotype
    ELSE NULLIF(tp.mom_genotype,'')
  END                                                           AS genotype,

  lc.clutch_code

FROM public.tank_pairs tp
LEFT JOIN public.tanks mt ON mt.tank_id = tp.mother_tank_id
LEFT JOIN public.tanks dt ON dt.tank_id = tp.father_tank_id
LEFT JOIN latest_clutch lc
  ON lc.fish_pair_id = tp.fish_pair_id AND lc.rn = 1
ORDER BY tp.created_at DESC NULLS LAST;

COMMENT ON VIEW public.v_tank_pairs IS
  'Snapshot-aware tank pairs (mother/father) with pretty helpers: pair_fish, pair_tanks, pair_genotype (and alias genotype) and latest clutch_code.';

-- Optional: remove the separate pretty view if it exists.
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.views
     WHERE table_schema='public' AND table_name='v_tank_pairs_pretty'
  ) THEN
    EXECUTE 'DROP VIEW public.v_tank_pairs_pretty';
  END IF;
END$$;

COMMIT;
