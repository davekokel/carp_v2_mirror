BEGIN;

DROP VIEW IF EXISTS public.v_transgenes_overview;

CREATE VIEW public.v_transgenes_overview AS
WITH allele_rollup AS (
  SELECT
    ta.transgene_base_code,
    COUNT(*)                                                          AS n_alleles,
    string_agg(ta.allele_number::text, ', ' ORDER BY ta.allele_number) AS allele_numbers,
    string_agg(ta.allele_nickname, ', ' ORDER BY ta.allele_number)      AS allele_nicknames
  FROM public.transgene_alleles ta
  GROUP BY ta.transgene_base_code
)
SELECT
  t.transgene_base_code,

  -- Construct wiring goes through constructs.base_code
  c.construct_code,
  c.construct_name,
  COALESCE(c.description, '')                         AS description,

  -- marker rollups in the three standard styles (from constructs overview)
  t.transgene_base_code                               AS marker_basecode_style,
  COALESCE(v.fusion_pretty,    '')                    AS marker_fluortag_style,
  COALESCE(v.organelle_fluors, '')                    AS marker_organelle_style,

  -- allele summary
  COALESCE(ar.n_alleles,       0)                     AS n_alleles,
  COALESCE(ar.allele_numbers,  '')                    AS allele_numbers,
  COALESCE(ar.allele_nicknames,'')                    AS allele_nicknames
FROM public.transgenes t
LEFT JOIN public.constructs c
  ON c.base_code = t.transgene_base_code
LEFT JOIN public.v_constructs_overview v
  ON v.construct_code = c.construct_code
LEFT JOIN allele_rollup ar
  ON ar.transgene_base_code = t.transgene_base_code
ORDER BY t.transgene_base_code;

COMMENT ON VIEW public.v_transgenes_overview IS
'v11 transgene overview: one row per transgene_base_code with true wiring via constructs.base_code, allele summary, and marker rollups joined from v_constructs_overview.';

COMMIT;
