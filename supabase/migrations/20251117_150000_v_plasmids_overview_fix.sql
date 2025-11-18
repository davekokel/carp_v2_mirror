BEGIN;

DROP VIEW IF EXISTS public.v_plasmids_overview;

CREATE VIEW public.v_plasmids_overview AS
WITH fusion_rollup AS (
  SELECT
    p.id AS plasmid_id,
    string_agg(DISTINCT fl.fluor_code, ', ' ORDER BY fl.fluor_code) AS fluors,
    string_agg(DISTINCT tg.tag_code, ', ' ORDER BY tg.tag_code)     AS tag_codes,
    string_agg(DISTINCT vfl.fusion_label, ', ' ORDER BY vfl.fusion_label) AS fusions,
    COUNT(DISTINCT jpf.fusion_id) AS n_fusions
  FROM public.plasmids p
  LEFT JOIN public.join_plasmid_fusions jpf
         ON jpf.plasmid_id = p.id
  LEFT JOIN public.fusions f
         ON f.id = jpf.fusion_id
  LEFT JOIN public.v_fusion_labels vfl
         ON vfl.fusion_id = f.id
  LEFT JOIN public.fluors fl
         ON fl.id = f.fluor_id
  LEFT JOIN public.tags tg
         ON tg.id = f.tag_id
  GROUP BY p.id
)
SELECT
  p.code,
  p.name,
  p.nickname,
  fr.fluors,
  fr.tag_codes,
  fr.fusions,
  fr.n_fusions,
  p.created_at
FROM public.plasmids p
LEFT JOIN fusion_rollup fr
       ON fr.plasmid_id = p.id;

COMMIT;
