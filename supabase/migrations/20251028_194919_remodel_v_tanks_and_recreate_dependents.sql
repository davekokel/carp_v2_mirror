BEGIN;

-- Drop in dependency order so we can change column sets safely
DROP VIEW IF EXISTS public.v_cross_clutch_instances;
DROP VIEW IF EXISTS public.v_fish_rich;
DROP VIEW IF EXISTS public.v_tank_pairs;
DROP VIEW IF EXISTS public.v_tanks;

-- v_tanks: membership-only (open), active tanks
CREATE VIEW public.v_tanks AS
SELECT
  t.tank_uuid::uuid         AS tank_uuid,
  t.tank_code::text         AS tank_code,
  t.status::text            AS status,
  t.created_at::timestamptz AS created_at,
  m.joined_at::timestamptz  AS joined_at,
  f.fish_uuid::uuid         AS fish_uuid,
  f.fish_code::text         AS fish_code
FROM public.fish_tank_memberships m
JOIN public.tanks t
  ON t.tank_uuid = m.tank_uuid
 AND t.status    = 'active'
JOIN public.fish f
  ON f.fish_uuid = m.fish_uuid
WHERE m.left_at IS NULL;

-- v_tank_pairs: do NOT depend on v_tanks; resolve codes from tanks + fish_pairs
CREATE VIEW public.v_tank_pairs AS
SELECT
  tp.tank_pair_code::text           AS tank_pair_code,
  fp.fish_pair_code::text           AS fish_pair_code,
  (SELECT f.fish_code FROM public.fish f WHERE f.fish_uuid = fp.mom_fish_id)::text AS mom_fish_code,
  (SELECT f.fish_code FROM public.fish f WHERE f.fish_uuid = fp.dad_fish_id)::text AS dad_fish_code,
  tm.tank_code::text                AS mother_tank_code,
  tf.tank_code::text                AS father_tank_code
FROM public.tank_pairs tp
LEFT JOIN public.fish_pairs fp ON fp.fish_pair_code = tp.fish_pair_code
LEFT JOIN public.tanks tm      ON tm.tank_uuid      = tp.mother_tank_id
LEFT JOIN public.tanks tf      ON tf.tank_uuid      = tp.father_tank_id;

-- v_fish_rich: enriched; counts via v_tanks (membership-only)
CREATE VIEW public.v_fish_rich AS
WITH tcounts AS (
  SELECT v.fish_code::text AS fish_code, COUNT(*)::int AS n_active_tanks
  FROM public.v_tanks v
  GROUP BY v.fish_code
),
alleles AS (
  SELECT
    f.fish_uuid,
    f.fish_code::text                         AS fish_code,
    fta.transgene_base_code                   AS transgene_base_code,
    fta.allele_number                         AS allele_number,
    ta.allele_nickname::text                  AS allele_nickname,
    ('gu' || fta.allele_number::text)         AS allele_code,
    ('Tg(' || fta.transgene_base_code || ')' ||
      ('gu' || fta.allele_number::text))      AS transgene_pretty
  FROM public.fish f
  LEFT JOIN public.fish_transgene_alleles fta
    ON fta.fish_uuid = f.fish_uuid
  LEFT JOIN public.transgene_alleles ta
    ON ta.transgene_base_code = fta.transgene_base_code
   AND ta.allele_number       = fta.allele_number
),
geno AS (
  SELECT
    a.fish_uuid,
    string_agg(a.transgene_pretty, '; ' ORDER BY a.transgene_pretty)::text AS genotype_rollup
  FROM alleles a
  GROUP BY a.fish_uuid
)
SELECT
  f.fish_uuid::uuid                           AS fish_uuid,
  f.fish_code::text                           AS fish_code,
  COALESCE(f.fish_name, f.name, '')::text     AS fish_name,
  COALESCE(f.fish_nickname, f.nickname, '')::text AS fish_nickname,
  f.genetic_background::text                  AS genetic_background,
  f.line_building_stage::text                 AS line_building_stage,
  f.date_birth::date                          AS date_birth,
  COALESCE(a.allele_number, 0)::int           AS allele_number,
  COALESCE(a.allele_code, '')::text           AS allele_code,
  COALESCE(tc.n_active_tanks, 0)::int         AS n_active_tanks,
  COALESCE(a.transgene_pretty, '')::text      AS transgene_pretty,
  COALESCE(g.genotype_rollup, '')::text       AS genotype_rollup,
  f.created_at::timestamptz                   AS created_at
FROM public.fish f
LEFT JOIN alleles a  ON a.fish_uuid  = f.fish_uuid
LEFT JOIN tcounts tc ON tc.fish_code = f.fish_code
LEFT JOIN geno g     ON g.fish_uuid  = f.fish_uuid
ORDER BY f.fish_code, a.transgene_pretty NULLS LAST;

-- v_cross_clutch_instances: match your final schema; uses v_tank_pairs and v_fish_rich genotypes
CREATE VIEW public.v_cross_clutch_instances AS
WITH mom AS (
  SELECT r.fish_code,
         r.genotype_rollup AS mom_genotype
  FROM public.v_fish_rich r
),
dad AS (
  SELECT r.fish_code,
         r.genotype_rollup AS dad_genotype
  FROM public.v_fish_rich r
)
SELECT
  x.id::uuid                    AS cross_instance_id,
  x.cross_run_code::text        AS cross_code,
  x.tank_pair_code::text        AS tank_pair_code,
  tp.fish_pair_code::text       AS fish_pair_code,
  tp.mom_fish_code::text        AS mom_fish_code,
  tp.dad_fish_code::text        AS dad_fish_code,
  tp.mother_tank_code::text     AS mom_tank_code,
  tp.father_tank_code::text     AS dad_tank_code,
  COALESCE(m.mom_genotype, ''::text) AS mom_genotype,
  COALESCE(d.dad_genotype, ''::text) AS dad_genotype,
  NULL::text                    AS clutch_genotype,
  (x.cross_date)::date          AS cross_date,
  x.created_at::timestamptz     AS cross_created_at,
  ci.id::uuid                   AS clutch_instance_id,
  ci.clutch_instance_code::text AS clutch_code,
  ci.created_at::timestamptz    AS clutch_created_at
FROM public.cross_instances x
LEFT JOIN public.v_tank_pairs tp ON tp.tank_pair_code = x.tank_pair_code
LEFT JOIN mom m ON m.fish_code = tp.mom_fish_code
LEFT JOIN dad d ON d.fish_code = tp.dad_fish_code
LEFT JOIN public.clutch_instances ci ON ci.cross_instance_id = x.id;

COMMIT;
