BEGIN;

-- Recreate with pretty strings added. Adapt the SELECT body to your current columns.
DROP VIEW IF EXISTS public.v_fish_standard_clean;

CREATE VIEW public.v_fish_standard_clean AS
WITH alleles AS (
  SELECT
    jfta.fish_id,
    jfta.transgene_base_code,
    jfta.allele_number,
    ta.allele_name,
    ta.allele_nickname
  FROM public.join_fish_transgene_alleles jfta
  JOIN public.transgene_alleles ta
    ON ta.transgene_base_code = jfta.transgene_base_code
   AND ta.allele_number       = jfta.allele_number
)
SELECT
  f.id           AS fish_id,
  f.fish_code,
  f.nickname,
  f.genetic_background,
  f.line_building_stage,
  f.birthday,
  -- rollups you already expose...
  COALESCE(a.transgene_base_code,'')  AS transgene_base_code,
  COALESCE(a.allele_nickname,'')      AS allele_nickname,
  COALESCE(a.allele_number,0)         AS allele_number,
  COALESCE(a.allele_name,'')          AS allele_name,
  'Tg('||COALESCE(a.transgene_base_code,'')||')'||COALESCE(a.allele_nickname,'') AS transgene_pretty_nickname,
  'Tg('||COALESCE(a.transgene_base_code,'')||')'||COALESCE(a.allele_name,'')     AS transgene_pretty_name
FROM public.fish f
LEFT JOIN LATERAL (
  -- pick the "latest" allele per fish if multiple exist; tweak ordering if you want
  SELECT *
  FROM alleles ax
  WHERE ax.fish_id = f.id
  ORDER BY ax.allele_number DESC
  LIMIT 1
) a ON true;

COMMIT;
