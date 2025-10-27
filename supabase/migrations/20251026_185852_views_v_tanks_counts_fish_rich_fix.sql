CREATE OR REPLACE VIEW public.v_tanks AS
SELECT
  t.tank_uuid,
  t.tank_code,
  t.status,
  t.created_at,
  regexp_replace(t.tank_code, '^TANK\(([^)]+)\)#\d+$', '\1')::text AS fish_code
FROM public.tanks t;

CREATE OR REPLACE VIEW public.v_fish_current_tank_counts AS
SELECT
  f.fish_uuid,
  COALESCE((
    SELECT COUNT(*) FROM public.v_tanks t
    WHERE t.status='active' AND t.fish_code = f.fish_code
  ),0)::int AS current_tanks
FROM public.fish f;

DROP VIEW IF EXISTS public.v_fish_rich;
CREATE VIEW public.v_fish_rich AS
WITH alleles AS (
  SELECT
    fta.fish_uuid,
    ta.transgene_base_code,
    ta.allele_number,
    ('gu' || ta.allele_number::text) AS allele_name,
    ta.allele_nickname,
    ('Tg('||ta.transgene_base_code||')'||'gu'||ta.allele_number::text) AS transgene_pretty_name
  FROM public.fish_transgene_alleles fta
  JOIN public.transgene_alleles ta
    ON ta.transgene_base_code = fta.transgene_base_code
   AND ta.allele_number       = fta.allele_number
),
allele_rollups AS (
  SELECT
    fish_uuid,
    ARRAY_AGG(allele_number ORDER BY transgene_pretty_name) AS allele_numbers,
    STRING_AGG(transgene_pretty_name, '; ' ORDER BY transgene_pretty_name) AS genotype_rollup_by_name
  FROM alleles
  GROUP BY fish_uuid
),
first_allele AS (
  SELECT DISTINCT ON (fish_uuid)
    fish_uuid, transgene_base_code, allele_number, allele_name, allele_nickname, transgene_pretty_name
  FROM alleles
  ORDER BY fish_uuid, transgene_pretty_name
)
SELECT
  f.fish_uuid,
  f.fish_code,
  f.genetic_background,
  f.line_building_stage,
  f.date_birth,
  COALESCE(cnt.current_tanks,0)::int AS n_active_tanks,
  CASE WHEN COALESCE(ARRAY_LENGTH(ar.allele_numbers,1),0)=0
       THEN 'WT('||COALESCE(f.genetic_background,'')||')'
       ELSE COALESCE(ar.genotype_rollup_by_name,'')
  END AS genotype_pretty,
  COALESCE(fa.allele_number, NULL) AS allele_number
FROM public.fish f
LEFT JOIN public.v_fish_current_tank_counts cnt ON cnt.fish_uuid = f.fish_uuid
LEFT JOIN first_allele  fa ON fa.fish_uuid = f.fish_uuid
LEFT JOIN allele_rollups ar ON ar.fish_uuid = f.fish_uuid;
