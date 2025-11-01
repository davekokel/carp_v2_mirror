BEGIN;
CREATE OR REPLACE VIEW public.v_fish_rich AS
WITH links AS (
  SELECT
    j.fish_id                 AS fish_uuid,
    j.transgene_base_code     AS base_code,
    j.allele_number           AS allele_number
  FROM public.join_fish_transgene_alleles j
),
alleles AS (
  SELECT
    l.fish_uuid,
    l.base_code,
    l.allele_number,
    ta.allele_name
  FROM links l
  JOIN public.transgene_alleles ta
    ON ta.transgene_base_code = l.base_code
   AND ta.allele_number       = l.allele_number
),
agg_inputs AS (
  SELECT
    a.fish_uuid,
    a.base_code,
    (a.base_code || '/' || a.allele_name)           AS acode,
    ('Tg(' || a.base_code || ')' || a.allele_name)  AS apretty
  FROM alleles a
),
agg AS (
  SELECT
    ai.fish_uuid,
    COUNT(*)::int                                                   AS allele_number,
    string_agg(DISTINCT ai.acode, ', ' ORDER BY ai.acode)          AS allele_code,
    string_agg(DISTINCT ai.base_code, ', ' ORDER BY ai.base_code)  AS transgene,
    string_agg(ai.apretty, '; ' ORDER BY ai.apretty)               AS genotype_rollup
  FROM agg_inputs ai
  GROUP BY ai.fish_uuid
),
tanks_agg AS (
  SELECT
    j.fish_id AS fish_uuid,
    COUNT(DISTINCT j.tank_id)::int AS n_active_tanks
  FROM public.join_fish_tanks j
  GROUP BY 1
)
SELECT
  f.id                   AS fish_uuid,
  f.fish_code            AS fish_code,
  f.name_human           AS fish_name,
  f.nickname             AS fish_nickname,
  f.genetic_background   AS genetic_background,
  f.line_building_stage  AS line_building_stage,
  f.description          AS description,
  f.dob                  AS dob,
  COALESCE(a.allele_number, 0)    AS allele_number,
  COALESCE(a.allele_code,   '')   AS allele_code,
  COALESCE(a.transgene,     '')   AS transgene,
  COALESCE(a.genotype_rollup, '') AS genotype_rollup,
  COALESCE(t.n_active_tanks, 0)   AS n_active_tanks,
  f.created_at           AS created_at
FROM public.fish f
LEFT JOIN agg       a ON a.fish_uuid = f.id
LEFT JOIN tanks_agg t ON t.fish_uuid = f.id
ORDER BY f.fish_code;
COMMIT;
