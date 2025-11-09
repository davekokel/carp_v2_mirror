BEGIN;

-- v_fluorescent_marker_rollup: prefer FT sources; fall back to plasmid/fusion sources; de-dupe.
CREATE OR REPLACE VIEW public.v_fluorescent_marker_rollup AS
WITH
-- FT-based source (join_fish_fluorescent_treatments + ft_proteins/ft_dyes)
ft_j AS (
  SELECT f.fish_code, jft.ft_code
  FROM public.join_fish_fluorescent_treatments jft
  JOIN public.fish f ON f.id = jft.fish_id
),
ft_prot AS (
  SELECT ft_j.fish_code,
         fp.fluor_code,
         fp.tag_code,
         (fp.fluor_code||'('||COALESCE(fp.tag_code,'')||')') AS marker,
         NULL::text AS dye_code
  FROM ft_j
  JOIN public.ft_proteins fp ON fp.ft_code = ft_j.ft_code
),
ft_dyes AS (
  SELECT ft_j.fish_code,
         NULL::text AS fluor_code,
         NULL::text AS tag_code,
         NULL::text AS marker,
         fd.dye_code
  FROM ft_j
  JOIN public.ft_dyes fd ON fd.ft_code = ft_j.ft_code
),
-- Fusion-based fallback (transgene_alleles -> plasmids -> fusions -> fluors/tags)
fu_base AS (
  SELECT f.fish_code, ta.transgene_base_code, ta.allele_number, p.id AS plasmid_id
  FROM public.fish f
  JOIN public.join_fish_transgene_alleles jf ON jf.fish_id = f.id
  JOIN public.transgene_alleles ta
    ON ta.transgene_base_code = jf.transgene_base_code
   AND ta.allele_number      = jf.allele_number
  JOIN public.plasmids p ON p.code = ta.transgene_base_code
),
fu_links AS (
  SELECT DISTINCT b.fish_code, fu.fluor_id, fu.tag_id, b.transgene_base_code, b.allele_number
  FROM fu_base b
  LEFT JOIN public.join_plasmid_fusions jpf ON jpf.plasmid_id = b.plasmid_id
  LEFT JOIN public.fusions fu ON fu.id = jpf.fusion_id
),
fu_named AS (
  SELECT l.fish_code,
         fl.fluor_name   AS fluor_code,  -- use names here as "codes" to show user-friendly strings
         tg.tag_name     AS tag_code,
         (
           CASE WHEN ta.allele_name IS NOT NULL AND ta.allele_name <> ''
                THEN (l.transgene_base_code||'('||ta.allele_name||')')
                ELSE l.transgene_base_code
           END
         ) AS marker,
         NULL::text      AS dye_code
  FROM fu_links l
  LEFT JOIN public.fluors fl ON fl.id = l.fluor_id
  LEFT JOIN public.tags   tg ON tg.id = l.tag_id
  LEFT JOIN public.transgene_alleles ta
    ON ta.transgene_base_code = l.transgene_base_code
   AND ta.allele_number      = l.allele_number
),
-- Union both sources
unioned AS (
  SELECT fish_code, fluor_code, tag_code, marker, dye_code FROM ft_prot
  UNION ALL
  SELECT fish_code, fluor_code, tag_code, marker, dye_code FROM ft_dyes
  UNION ALL
  SELECT fish_code, fluor_code, tag_code, marker, dye_code FROM fu_named
),
agg AS (
  SELECT
    fish_code,
    COALESCE(string_agg(DISTINCT marker,     ',' ORDER BY marker),     '') AS markers,
    COALESCE(string_agg(DISTINCT fluor_code, ',' ORDER BY fluor_code), '') AS fluors,
    COALESCE(string_agg(DISTINCT tag_code,   ',' ORDER BY tag_code),   '') AS tags,
    COALESCE(string_agg(DISTINCT dye_code,   ',' ORDER BY dye_code),   '') AS dyes
  FROM unioned
  GROUP BY fish_code
)
SELECT f.fish_code,
       COALESCE(a.markers,'') AS markers,
       COALESCE(a.fluors,'')  AS fluors,
       COALESCE(a.tags,'')    AS tags,
       COALESCE(a.dyes,'')    AS dyes
FROM public.fish f
LEFT JOIN agg a ON a.fish_code = f.fish_code;

COMMIT;
