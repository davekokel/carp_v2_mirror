BEGIN;
DROP VIEW IF EXISTS public.v_fish_rich;
CREATE VIEW public.v_fish_rich AS
WITH alleles AS (
  SELECT
    fta.fish_uuid,
    ta.transgene_base_code,
    ta.allele_number,
    ('gu' || ta.allele_number::text) AS allele_name,
    ta.allele_nickname,
    ('Tg('||ta.transgene_base_code||')'||COALESCE(ta.allele_nickname, 'gu'||ta.allele_number::text)) AS transgene_pretty_nickname,
    ('Tg('||ta.transgene_base_code||')'||'gu'||ta.allele_number::text) AS transgene_pretty_name
  FROM public.fish_transgene_alleles fta
  JOIN public.transgene_alleles ta
    ON ta.transgene_base_code = fta.transgene_base_code
   AND ta.allele_number       = fta.allele_number
),
allele_rollups AS (
  SELECT
    fish_uuid,
    ARRAY_AGG(allele_number   ORDER BY transgene_pretty_name)                 AS allele_numbers,
    ARRAY_AGG(allele_name     ORDER BY transgene_pretty_name)                 AS allele_names,
    ARRAY_AGG(allele_nickname ORDER BY transgene_pretty_name)                 AS allele_nicknames,
    STRING_AGG(transgene_pretty_nickname, '; ' ORDER BY transgene_pretty_nickname) AS genotype_rollup_by_nickname,
    STRING_AGG(transgene_pretty_name,     '; ' ORDER BY transgene_pretty_name)     AS genotype_rollup_by_name
  FROM alleles
  GROUP BY fish_uuid
),
first_allele AS (
  SELECT DISTINCT ON (fish_uuid)
    fish_uuid,
    transgene_base_code,
    allele_number,
    allele_name,
    allele_nickname,
    transgene_pretty_nickname,
    transgene_pretty_name
  FROM alleles
  ORDER BY fish_uuid, transgene_pretty_name
)
SELECT
  f.fish_uuid,
  f.fish_code,
  NULL::text AS fish_name,
  NULL::text AS fish_nickname,
  f.genetic_background,
  f.line_building_stage,
  f.date_birth,
  COALESCE((
    SELECT COUNT(*) FROM public.tanks t
    WHERE t.status='active'
      AND t.tank_code LIKE ('TANK('||f.fish_code||')#%')
  ),0)::int AS n_active_tanks,
  COALESCE(fa.allele_nickname,'')          AS allele_nickname,
  fa.allele_number,
  COALESCE(fa.allele_name,'')              AS allele_name,
  COALESCE(fa.transgene_pretty_nickname,'') AS transgene_pretty_nickname,
  COALESCE(fa.transgene_pretty_name,'')     AS transgene_pretty_name,
  COALESCE(ar.allele_numbers,   ARRAY[]::int[])   AS allele_numbers,
  COALESCE(ar.allele_names,     ARRAY[]::text[])  AS allele_names,
  COALESCE(ar.allele_nicknames, ARRAY[]::text[])  AS allele_nicknames,
  COALESCE(ar.genotype_rollup_by_nickname,'')     AS genotype_rollup_by_nickname,
  COALESCE(ar.genotype_rollup_by_name,'')         AS genotype_rollup_by_name,
  (COALESCE(ARRAY_LENGTH(ar.allele_numbers,1),0)=0) AS is_wildtype,
  CASE WHEN COALESCE(ARRAY_LENGTH(ar.allele_numbers,1),0)=0
       THEN 'WT('||COALESCE(f.genetic_background,'')||')'
       ELSE COALESCE(ar.genotype_rollup_by_name,'')
  END AS genotype_pretty,
  f.created_at,
  f.updated_at
FROM public.fish f
LEFT JOIN first_allele  fa ON fa.fish_uuid = f.fish_uuid
LEFT JOIN allele_rollups ar ON ar.fish_uuid = f.fish_uuid;
COMMIT;
