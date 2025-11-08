BEGIN;

DROP VIEW IF EXISTS public.v_fish_main;

CREATE VIEW public.v_fish_main AS
WITH alleles AS (
  SELECT
    f.fish_code,
    jfta.transgene_base_code,
    jfta.allele_number,
    ta.allele_name,
    ta.allele_nickname
  FROM public.fish f
  JOIN public.join_fish_transgene_alleles jfta ON jfta.fish_id = f.id
  JOIN public.transgene_alleles ta
    ON ta.transgene_base_code = jfta.transgene_base_code
   AND ta.allele_number       = jfta.allele_number
),
pick AS (
  SELECT DISTINCT ON (a.fish_code)
         a.fish_code, a.transgene_base_code, a.allele_number, a.allele_name, a.allele_nickname
  FROM alleles a
  ORDER BY a.fish_code, a.allele_number DESC
)
SELECT
  v.*,
  COALESCE(pick.transgene_base_code,'') AS transgene_base_code,
  COALESCE(pick.allele_nickname,'')     AS allele_nickname,
  COALESCE(pick.allele_number,0)        AS allele_number,
  COALESCE(pick.allele_name,'')         AS allele_name,
  'Tg('||COALESCE(pick.transgene_base_code,'')||')'||COALESCE(pick.allele_nickname,'') AS transgene_pretty_nickname,
  'Tg('||COALESCE(pick.transgene_base_code,'')||')'||COALESCE(pick.allele_name,'')     AS transgene_pretty_name
FROM public.v_fish_overview_id v
LEFT JOIN pick ON pick.fish_code = v.fish_code;

COMMIT;
