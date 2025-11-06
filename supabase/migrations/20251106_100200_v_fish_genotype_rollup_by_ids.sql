BEGIN;
CREATE OR REPLACE VIEW public.v_fish_genotype_rollup_by_ids
(fish_id, allele_count, allele_codes, allele_nicknames, transgenes, genotype_rollup)
AS
WITH jt AS (
  SELECT
    j.fish_id,
    ga.transgene_base_code,
    ga.allele_number,
    COALESCE(NULLIF(j.zygosity,''),'unk') AS zygosity,
    NULLIF(ga.allele_nickname,'') AS allele_nickname
  FROM public.join_fish_transgene_alleles j
  JOIN public.transgene_alleles ga
    ON ga.transgene_base_code = j.transgene_base_code
   AND ga.allele_number       = j.allele_number
)
SELECT
  fish_id,
  COUNT(*)::int AS allele_count,
  COALESCE(NULLIF(string_agg(DISTINCT (transgene_base_code||':'||allele_number), ', '),''),'') AS allele_codes,
  COALESCE(NULLIF(string_agg(DISTINCT COALESCE(allele_nickname,''), ', '),''),'') AS allele_nicknames,
  COALESCE(NULLIF(string_agg(DISTINCT transgene_base_code, ', '),''),'') AS transgenes,
  COALESCE(NULLIF(string_agg(DISTINCT
           (transgene_base_code||':'||allele_number||
            CASE WHEN zygosity IS NOT NULL THEN ' ('||zygosity||')' ELSE '' END),
           ', '),''),'') AS genotype_rollup
FROM jt
GROUP BY fish_id;
COMMIT;
