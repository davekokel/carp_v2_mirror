BEGIN;

DROP VIEW IF EXISTS public.v_fusions_overview;

CREATE VIEW public.v_fusions_overview AS
SELECT
  f.id,
  -- fusion_name: fluor::tag(tag_pos) when tag exists, otherwise just fluor
  COALESCE(fl.fluor_code, '') ||
  CASE
    WHEN t.tag_code IS NOT NULL AND t.tag_code <> ''
      THEN '::' || t.tag_code ||
           CASE
             WHEN f.tag_pos IS NOT NULL AND f.tag_pos <> ''
               THEN '(' || f.tag_pos || ')'
             ELSE ''
           END
    ELSE ''
  END AS fusion_name,
  fl.fluor_code AS fluor,
  t.tag_code    AS tag,
  f.tag_pos,
  COUNT(DISTINCT cf.construct_id) AS n_constructs,
  f.created_at
FROM public.fusions f
LEFT JOIN public.fluors   fl ON fl.id = f.fluor_id
LEFT JOIN public.tags     t  ON t.id  = f.tag_id
LEFT JOIN public.construct_fusions cf ON cf.fusion_id = f.id
GROUP BY
  f.id,
  fl.fluor_code,
  t.tag_code,
  f.tag_pos,
  f.created_at
ORDER BY f.created_at DESC;

COMMIT;
