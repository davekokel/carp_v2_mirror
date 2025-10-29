BEGIN;

DROP VIEW IF EXISTS public.v_fish_rich;
DROP VIEW IF EXISTS public.v_tanks;

CREATE VIEW public.v_tanks
(tank_uuid, tank_code, status, created_at, fish_code, fish_uuid, started_at, ended_at, is_active) AS
SELECT
  t.tank_uuid::uuid,
  t.tank_code::text,
  t.status::text,
  t.created_at::timestamptz,
  f.fish_code::text,
  f.fish_uuid::uuid,
  m.joined_at::timestamptz,
  m.left_at::timestamptz,
  (m.left_at IS NULL)
FROM public.fish_tank_memberships m
JOIN public.tanks t ON t.tank_uuid = m.tank_uuid AND t.status = 'active'
JOIN public.fish  f ON f.fish_uuid = m.fish_uuid
WHERE m.left_at IS NULL;

CREATE VIEW public.v_fish_rich AS
WITH tcounts AS (
  SELECT v.fish_code::text AS fish_code, COUNT(*)::int AS n_active_tanks
  FROM public.v_tanks v
  GROUP BY v.fish_code
), alleles AS (
  SELECT
    f.fish_uuid,
    f.fish_code::text                 AS fish_code,
    fta.transgene_base_code           AS transgene_base_code,
    fta.allele_number                 AS allele_number,
    ta.allele_nickname::text          AS allele_nickname,
    ('gu' || fta.allele_number::text) AS allele_code,
    ('Tg(' || fta.transgene_base_code || ')' || ('gu' || fta.allele_number::text)) AS transgene_pretty
  FROM public.fish f
  LEFT JOIN public.fish_transgene_alleles fta ON fta.fish_uuid = f.fish_uuid
  LEFT JOIN public.transgene_alleles ta ON ta.transgene_base_code = fta.transgene_base_code AND ta.allele_number = fta.allele_number
), geno AS (
  SELECT a.fish_uuid, string_agg(a.transgene_pretty, '; ' ORDER BY a.transgene_pretty)::text AS genotype_rollup
  FROM alleles a
  GROUP BY a.fish_uuid
)
SELECT
  f.fish_uuid::uuid                 AS fish_uuid,
  f.fish_code::text                 AS fish_code,
  (CASE WHEN f.fish_name IS NOT NULL THEN f.fish_name ELSE f.name END)::text AS fish_name,
  (CASE WHEN f.fish_nickname IS NOT NULL THEN f.fish_nickname ELSE f.nickname END)::text AS fish_nickname,
  f.genetic_background::text        AS genetic_background,
  f.line_building_stage::text       AS line_building_stage,
  f.date_birth::date                AS date_birth,
  a.allele_number                   AS allele_number,
  a.allele_code::text               AS allele_code,
  tcounts.n_active_tanks            AS n_active_tanks,
  a.transgene_pretty::text          AS transgene_pretty,
  g.genotype_rollup::text           AS genotype_rollup,
  f.created_at::timestamptz         AS created_at
FROM public.fish f
LEFT JOIN alleles a  ON a.fish_uuid  = f.fish_uuid
LEFT JOIN tcounts    ON tcounts.fish_code = f.fish_code
LEFT JOIN geno g     ON g.fish_uuid  = f.fish_uuid
ORDER BY f.fish_code, a.transgene_pretty NULLS LAST;

COMMIT;
