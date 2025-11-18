BEGIN;

CREATE OR REPLACE VIEW public.v_fusion_labels AS
SELECT
  f.id           AS fusion_id,
  fl.fluor_code,
  tg.tag_code,
  f.tag_pos,
  CASE
    WHEN fl.fluor_code IS NULL AND tg.tag_code IS NULL THEN ''
    WHEN fl.fluor_code IS NULL THEN
      tg.tag_code ||
      CASE
        WHEN f.tag_pos IS NULL OR f.tag_pos = '' THEN ''
        ELSE '(' || f.tag_pos::text || ')'
      END
    WHEN tg.tag_code IS NULL THEN
      fl.fluor_code ||
      CASE
        WHEN f.tag_pos IS NULL OR f.tag_pos = '' THEN ''
        ELSE '(' || f.tag_pos::text || ')'
      END
    ELSE
      fl.fluor_code || ':' || tg.tag_code ||
      CASE
        WHEN f.tag_pos IS NULL OR f.tag_pos = '' THEN ''
        ELSE '(' || f.tag_pos::text || ')'
      END
  END            AS fusion_label,
  f.created_at
FROM public.fusions f
LEFT JOIN public.fluors fl ON fl.id = f.fluor_id
LEFT JOIN public.tags   tg ON tg.id = f.tag_id;

COMMIT;
