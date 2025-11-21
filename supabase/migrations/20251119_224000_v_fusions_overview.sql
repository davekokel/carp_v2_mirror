BEGIN;

CREATE OR REPLACE VIEW public.v_fusions_overview AS
WITH agg AS (
  SELECT
    f.id,
    CASE
      WHEN fl.fluor_code IS NULL AND tg.tag_code IS NULL THEN
        'fusion ' || f.id::text
      WHEN fl.fluor_code IS NOT NULL AND tg.tag_code IS NULL THEN
        fl.fluor_code
      WHEN fl.fluor_code IS NULL AND tg.tag_code IS NOT NULL THEN
        tg.tag_code
      WHEN fl.fluor_code IS NOT NULL AND tg.tag_code IS NOT NULL
           AND f.tag_pos IS NOT NULL AND f.tag_pos <> '' THEN
        fl.fluor_code || '::' || tg.tag_code || '(' || f.tag_pos || ')'
      ELSE
        fl.fluor_code || '::' || tg.tag_code
    END AS fusion_name,
    COALESCE(fl.fluor_code, '')   AS fluor,
    COALESCE(tg.tag_code, '')     AS tag,
    COALESCE(f.tag_pos::text, '') AS tag_pos,
    COUNT(DISTINCT jpf.plasmid_id) AS n_plasmids,
    COUNT(DISTINCT jrf.rna_id)     AS n_rnas,
    f.created_at
  FROM public.fusions f
  LEFT JOIN public.fluors fl ON fl.id = f.fluor_id
  LEFT JOIN public.tags   tg ON tg.id = f.tag_id
  LEFT JOIN public.join_plasmid_fusions jpf ON jpf.fusion_id = f.id
  LEFT JOIN public.join_rna_fusions     jrf ON jrf.fusion_id = f.id
  GROUP BY
    f.id,
    fl.fluor_code,
    tg.tag_code,
    f.tag_pos,
    f.created_at
)
SELECT
  id,
  fusion_name,
  fluor,
  tag,
  tag_pos,
  n_plasmids,
  n_rnas,
  created_at
FROM agg;

COMMIT;
