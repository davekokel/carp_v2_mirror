DROP VIEW IF EXISTS public.v_fish_rich;
DROP VIEW IF EXISTS public.v_fish_current_tank_counts;
DROP VIEW IF EXISTS public.v_tanks;

CREATE VIEW public.v_tanks AS
SELECT
  t.tank_uuid,
  t.tank_code,
  t.status,
  t.created_at,
  COALESCE(NULLIF(t.fish_code, ''), regexp_replace(t.tank_code, '^TANK\(([^)]+)\)#\d+$', '\1'))::text AS fish_code
FROM public.tanks t;

CREATE VIEW public.v_fish_current_tank_counts AS
SELECT
  f.fish_uuid,
  COALESCE((
    SELECT COUNT(*) FROM public.v_tanks t
    WHERE t.status = 'active' AND t.fish_code = f.fish_code
  ), 0)::int AS current_tanks
FROM public.fish f;

CREATE VIEW public.v_fish_rich AS
WITH alleles AS (
  SELECT
    fta.fish_uuid,
    fta.transgene_base_code,
    fta.allele_number,
    COALESCE(ta.allele_number::text, NULL) AS allele_number_text,
    COALESCE(ta.allele_name, 'gu' || fta.allele_number::text) AS allele_name,
    ('Tg(' || fta.transgene_base_code || ')' || COALESCE(ta.allele_name, 'gu' || fta.allele_number::text)) AS transgene_pretty
  FROM public.fish_transgene_alleles fta
  LEFT JOIN public.transgene_alleles ta
    ON ta.transgene_base_code = fta.transgene_base_code
   AND ta.allele_number       = fta.allele_number
),
allele_rollups AS (
  SELECT
    fish_uuid,
    STRING_AGG(transgene_pretty, '; ' ORDER BY transgene_pretty) AS genotype_rollup
  FROM alleles
  GROUP BY fish_uuid
),
first_allele AS (
  SELECT DISTINCT ON (fish_uuid)
    fish_uuid,
    transgene_base_code,
    allele_number,
    (transgene_base_code || '_' || allele_number)::text AS allele_code,
    ('Tg(' || transgene_base_code || ')' || COALESCE(NULLIF(allele_number_text,''), 'gu' || allele_number::text)) AS transgene_pretty
  FROM alleles
  ORDER BY fish_uuid, transgene_base_code, allele_number
)
SELECT
  f.fish_uuid,
  f.fish_code,
  COALESCE(f.name, NULL)      AS fish_name,
  COALESCE(f.nickname, NULL)  AS fish_nickname,
  f.genetic_background,
  f.line_building_stage,
  f.date_birth,
  COALESCE(cnt.current_tanks, 0)::int AS n_active_tanks,
  fa.allele_number,
  fa.allele_code,
  COALESCE(fa.transgene_pretty, 'WT(' || COALESCE(f.genetic_background,'') || ')') AS transgene_pretty,
  COALESCE(ar.genotype_rollup,  'WT(' || COALESCE(f.genetic_background,'') || ')') AS genotype_rollup,
  f.created_at
FROM public.fish f
LEFT JOIN public.v_fish_current_tank_counts cnt ON cnt.fish_uuid = f.fish_uuid
LEFT JOIN first_allele fa ON fa.fish_uuid = f.fish_uuid
LEFT JOIN allele_rollups ar ON ar.fish_uuid = f.fish_uuid;
