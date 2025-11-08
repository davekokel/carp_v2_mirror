BEGIN;

-- Recreate v_fish_unified using a marker_label subquery so DISTINCT + ORDER BY match
DROP VIEW IF EXISTS public.v_fish_unified;

CREATE VIEW public.v_fish_unified AS
WITH gp AS (
  SELECT
    m.fish_code,
    string_agg(DISTINCT m.marker_label, ', ' ORDER BY m.marker_label) AS genotype_pretty
  FROM (
    SELECT
      f.fish_code,
      (ta.transgene_base_code || '(' || ta.allele_name || ')')::text AS marker_label
    FROM public.join_fish_transgene_alleles jf
    JOIN public.fish f
      ON f.id = jf.fish_id
    JOIN public.transgene_alleles ta
      ON ta.transgene_base_code = jf.transgene_base_code
     AND ta.allele_number      = jf.allele_number
    WHERE ta.allele_name IS NOT NULL AND ta.allele_name <> ''
  ) AS m
  GROUP BY m.fish_code
),
mr AS (
  SELECT r.fish_code, r.markers, r.fluors, r.tags, r.dyes
  FROM public.v_fluorescent_marker_rollup r
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
