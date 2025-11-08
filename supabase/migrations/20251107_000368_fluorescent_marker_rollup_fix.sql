BEGIN;

DROP VIEW IF EXISTS public.v_fluorescent_marker_rollup;

CREATE VIEW public.v_fluorescent_marker_rollup AS
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
  SELECT DISTINCT
    b.fish_code,
    b.transgene_base_code,
    b.allele_number,
    fu.fluor_id,
    fu.tag_id,
    fu.dye_id
  FROM base b
  LEFT JOIN public.join_plasmid_fusions jpf
    ON jpf.plasmid_id = b.plasmid_id
  LEFT JOIN public.fusions fu
    ON fu.id = jpf.fusion_id
)
SELECT
  b.fish_code,
  string_agg(DISTINCT b.transgene_base_code || b.allele_number::text, ',' ORDER BY b.transgene_base_code, b.allele_number) AS markers,
  string_agg(DISTINCT fl.name, ',' ORDER BY fl.name) AS fluors,
  string_agg(DISTINCT tg.name, ',' ORDER BY tg.name) AS tags,
  string_agg(DISTINCT dy.name, ',' ORDER BY dy.name) AS dyes
FROM base b
LEFT JOIN fus x
  ON x.fish_code=b.fish_code AND x.transgene_base_code=b.transgene_base_code AND x.allele_number=b.allele_number
LEFT JOIN public.fluors fl ON fl.id = x.fluor_id
LEFT JOIN public.tags   tg ON tg.id = x.tag_id
LEFT JOIN public.dyes   dy ON dy.id = x.dye_id
GROUP BY b.fish_code;

COMMIT;
