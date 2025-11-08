BEGIN;

-- single, canonical fish view with pretty genotype + marker rollup
CREATE OR REPLACE VIEW public.v_fish_unified AS
WITH gp AS (
  SELECT
    f.fish_code,
    string_agg(
      DISTINCT (ta.transgene_base_code || COALESCE('('||ta.allele_name||')','')),
      ', ' ORDER BY (ta.transgene_base_code || COALESCE('('||ta.allele_name||')',''))
    ) AS genotype_pretty
  FROM public.fish f
  JOIN public.join_fish_transgene_alleles jf
    ON jf.fish_id = f.id
  JOIN public.transgene_alleles ta
    ON ta.transgene_base_code = jf.transgene_base_code
   AND ta.allele_number       = jf.allele_number
  GROUP BY f.fish_code
),
mr AS (
  SELECT
    fish_code,
    COALESCE(markers,'') AS markers,
    COALESCE(fluors ,'') AS fluors,
    COALESCE(tags   ,'') AS tags,
    COALESCE(dyes   ,'') AS dyes
  FROM public.v_fluorescent_marker_rollup
)
SELECT
  vfm.*,
  COALESCE(gp.genotype_pretty,'') AS genotype_pretty,
  COALESCE(mr.markers,'')         AS markers,
  COALESCE(mr.fluors,'')          AS fluors,
  COALESCE(mr.tags,'')            AS tags,
  COALESCE(mr.dyes,'')            AS dyes
FROM public.v_fish_main vfm
LEFT JOIN gp ON gp.fish_code = vfm.fish_code
LEFT JOIN mr ON mr.fish_code = vfm.fish_code;

COMMIT;
