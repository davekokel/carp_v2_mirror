BEGIN;

CREATE OR REPLACE VIEW public.v_fusion_labels AS
SELECT
  f.id AS fusion_id,
  fl.fluor_code,
  tg.tag_code,
  f.tag_pos,
  CASE
    WHEN f.tag_id IS NULL THEN fl.fluor_code
    WHEN f.tag_pos IS NULL THEN fl.fluor_code || '::' || tg.tag_code
    ELSE fl.fluor_code || '::' || tg.tag_code || '(' || f.tag_pos || ')'
  END AS fusion_label
FROM public.fusions f
JOIN public.fluors fl ON fl.id = f.fluor_id
LEFT JOIN public.tags tg ON tg.id = f.tag_id;

COMMIT;
