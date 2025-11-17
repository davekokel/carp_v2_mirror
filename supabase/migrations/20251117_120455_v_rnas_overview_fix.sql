BEGIN;

DROP VIEW IF EXISTS public.v_rnas_overview;

CREATE VIEW public.v_rnas_overview AS
WITH rna_fusions AS (
  SELECT
    r.rna_base_code,
    r.name,
    r.created_at,
    jrf.fusion_id,
    vfl.fusion_label,
    vfl.fluor_code,
    vfl.tag_code
  FROM public.rnas AS r
  LEFT JOIN public.join_rna_fusions AS jrf
    ON jrf.rna_id = r.id
  LEFT JOIN public.v_fusion_labels AS vfl
    ON vfl.fusion_id = jrf.fusion_id
)
SELECT
  rna_base_code,
  NULL::text AS nickname,
  name,
  string_agg(DISTINCT fluor_code, ', ' ORDER BY fluor_code)      AS fluors,
  string_agg(DISTINCT tag_code,   ', ' ORDER BY tag_code)        AS tag_codes,
  string_agg(DISTINCT fusion_label, '; ' ORDER BY fusion_label)  AS fusions,
  COUNT(DISTINCT fusion_id)                                      AS n_fusions,
  MIN(created_at)                                                AS created_at
FROM rna_fusions
GROUP BY
  rna_base_code,
  name;

COMMIT;
