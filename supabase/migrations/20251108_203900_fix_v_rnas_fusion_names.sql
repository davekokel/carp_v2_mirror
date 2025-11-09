BEGIN;

DROP VIEW IF EXISTS public.v_rnas;

-- Rebuild v_rnas with three pre-deduped contexts (fusions, fluors, tags)
CREATE OR REPLACE VIEW public.v_rnas AS
WITH ctx_fusions AS (
  SELECT
    s.rna_code,
    string_agg(s.fusion_name, ', ' ORDER BY s.fusion_name) AS fusion_names
  FROM (
    SELECT DISTINCT
      rp.rna_code,
      f.fusion_name
    FROM public.rna_proteins rp
    LEFT JOIN public.fluors  fl ON fl.fluor_code = rp.fluor_code
    LEFT JOIN public.tags    tg ON tg.tag_code   = rp.tag_code
    LEFT JOIN public.fusions f
      ON f.fluor_id = fl.id
     AND (
          (f.tag_id IS NULL AND rp.tag_code IS NULL)
       OR  f.tag_id = tg.id
     )
    WHERE f.fusion_name IS NOT NULL AND f.fusion_name <> ''
  ) AS s
  GROUP BY s.rna_code
),
ctx_fluors AS (
  SELECT
    t.rna_code,
    string_agg(t.fluor_val, ', ' ORDER BY t.fluor_val) AS fluor_names
  FROM (
    SELECT DISTINCT
      rp.rna_code,
      COALESCE(fl.fluor_name, fl.fluor_code) AS fluor_val
    FROM public.rna_proteins rp
    LEFT JOIN public.fluors fl ON fl.fluor_code = rp.fluor_code
    WHERE COALESCE(fl.fluor_name, fl.fluor_code) IS NOT NULL
  ) AS t
  GROUP BY t.rna_code
),
ctx_tags AS (
  SELECT
    t.rna_code,
    string_agg(t.tag_val, ', ' ORDER BY t.tag_val) AS tag_names
  FROM (
    SELECT DISTINCT
      rp.rna_code,
      COALESCE(tg.tag_name, tg.tag_code) AS tag_val
    FROM public.rna_proteins rp
    LEFT JOIN public.tags tg ON tg.tag_code = rp.tag_code
    WHERE COALESCE(tg.tag_name, tg.tag_code) IS NOT NULL
  ) AS t
  GROUP BY t.rna_code
)
SELECT
  r.rna_code,
  r.rna_name,
  r.base_plasmid_code,
  r.genetic_element,
  COALESCE(cf.fusion_names,'') AS fusion_names,
  COALESCE(cfl.fluor_names,'') AS fluor_names,
  COALESCE(ct.tag_names,'')    AS tag_names,
  COALESCE(r.notes,'')         AS notes,
  r.created_by,
  r.created_at
FROM public.rnas r
LEFT JOIN ctx_fusions cf ON cf.rna_code = r.rna_code
LEFT JOIN ctx_fluors  cfl ON cfl.rna_code = r.rna_code
LEFT JOIN ctx_tags    ct  ON ct.rna_code  = r.rna_code
ORDER BY r.created_at DESC, r.rna_code;

COMMIT;
