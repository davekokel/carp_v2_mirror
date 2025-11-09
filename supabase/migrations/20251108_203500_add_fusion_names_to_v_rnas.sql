BEGIN;

DROP VIEW IF EXISTS public.v_rnas;

CREATE OR REPLACE VIEW public.v_rnas AS
WITH ctx AS (
  SELECT
    rp.rna_code,
    string_agg(DISTINCT f.fusion_name, ', ' ORDER BY f.fusion_name) AS fusion_names,
    string_agg(DISTINCT fl.fluor_name, ', ' ORDER BY fl.fluor_name) AS fluor_names,
    string_agg(
      DISTINCT COALESCE(tg.tag_name, tg.tag_code),
      ', ' ORDER BY 1
    ) AS tag_names
  FROM public.rna_proteins rp
  LEFT JOIN public.fluors fl ON fl.fluor_code = rp.fluor_code
  LEFT JOIN public.tags   tg ON tg.tag_code   = rp.tag_code
  LEFT JOIN public.fusions f
    ON (f.fluor_id = fl.id AND (f.tag_id = tg.id OR (f.tag_id IS NULL AND rp.tag_code IS NULL)))
  GROUP BY rp.rna_code
)
SELECT
  r.rna_code,
  r.rna_name,
  r.base_plasmid_code,
  r.genetic_element,
  COALESCE(ctx.fusion_names,'') AS fusion_names,
  COALESCE(ctx.fluor_names,'')  AS fluor_names,
  COALESCE(ctx.tag_names,'')    AS tag_names,
  COALESCE(r.notes,'')          AS notes,
  r.created_by,
  r.created_at
FROM public.rnas r
LEFT JOIN ctx ON ctx.rna_code = r.rna_code
ORDER BY r.created_at DESC, r.rna_code;

COMMIT;
