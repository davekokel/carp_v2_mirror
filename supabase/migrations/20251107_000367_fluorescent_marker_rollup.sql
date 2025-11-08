BEGIN;

CREATE OR REPLACE VIEW public.v_fluorescent_marker_rollup AS
WITH base AS (
  SELECT
    f.fish_code,
    ta.transgene_base_code,
    ta.allele_number,
    p.id AS plasmid_id
  FROM public.fish f
  JOIN public.join_fish_transgene_alleles jf
    ON jf.fish_id = f.id
  JOIN public.transgene_alleles ta
    ON ta.transgene_base_code = jf.transgene_base_code
   AND ta.allele_number       = jf.allele_number
  JOIN public.plasmids p
    ON p.code = ta.transgene_base_code
),
fus AS (
  SELECT
    b.fish_code,
    b.transgene_base_code,
    b.allele_number,
    COALESCE(fu.fluor_id,  fu2.fluor_id)  AS fluor_id,
    COALESCE(fu.tag_id,    fu2.tag_id)    AS tag_id,
    COALESCE(fu.dye_id,    fu2.dye_id)    AS dye_id
  FROM base b
  LEFT JOIN public.fusions fu
    ON fu.plasmid_id = b.plasmid_id
  LEFT JOIN public.join_plasmid_fusions jpf
    ON jpf.plasmid_id = b.plasmid_id
  LEFT JOIN public.fusions fu2
    ON fu2.id = jpf.fusion_id
)
SELECT
  b.fish_code,
  string_agg(DISTINCT b.transgene_base_code || b.allele_number::text, ',' ORDER BY b.transgene_base_code, b.allele_number) AS markers,
  string_agg(DISTINCT fn.name, ',' ORDER BY fn.name) AS fluors,
  string_agg(DISTINCT tn.name, ',' ORDER BY tn.name) AS tags,
  string_agg(DISTINCT dn.name, ',' ORDER BY dn.name) AS dyes
FROM base b
LEFT JOIN fus x
  ON x.fish_code=b.fish_code AND x.transgene_base_code=b.transgene_base_code AND x.allele_number=b.allele_number
LEFT JOIN public.fluors fn ON fn.id = x.fluor_id
LEFT JOIN public.tags   tn ON tn.id = x.tag_id
LEFT JOIN public.dyes   dn ON dn.id = x.dye_id
GROUP BY b.fish_code;

COMMIT;
