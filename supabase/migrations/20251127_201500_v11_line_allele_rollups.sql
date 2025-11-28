BEGIN;

DROP VIEW IF EXISTS public.v11_line_allele_rollups;

CREATE VIEW public.v11_line_allele_rollups AS
WITH per_allele AS (
  SELECT
    fl.id AS line_id,

    -- canonical: Tg(basecode)allele_name
    'Tg(' || ta.transgene_base_code || ')' ||
      COALESCE(ta.allele_name, '') AS canonical,

    -- label: Tg(basecode)nickname_or_name (nickname if present, else allele_name)
    'Tg(' || ta.transgene_base_code || ')' ||
      COALESCE(NULLIF(ta.allele_nickname, ''), ta.allele_name, '') AS label
  FROM public.fish_lines fl
  JOIN public.join_line_alleles jla
    ON jla.line_id = fl.id
  JOIN public.constructs c
    ON c.id = jla.construct_id
  JOIN public.transgene_alleles ta
    ON ta.transgene_base_code = c.base_code
   AND ta.allele_number       = jla.allele_number
)
SELECT
  line_id,
  string_agg(DISTINCT canonical, '; ' ORDER BY canonical) AS allele_canonical_rollup,
  string_agg(DISTINCT label,     '; ' ORDER BY label)     AS allele_label_rollup
FROM per_allele
GROUP BY line_id;

COMMIT;
