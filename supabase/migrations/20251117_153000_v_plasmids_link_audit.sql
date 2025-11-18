BEGIN;

DROP VIEW IF EXISTS public.v_plasmids_link_audit;

CREATE VIEW public.v_plasmids_link_audit AS
WITH fusion_rollup AS (
  SELECT
    p.id AS plasmid_id,
    COUNT(DISTINCT jpf.fusion_id) AS n_fusions,
    string_agg(DISTINCT fl.fluor_code, ', ' ORDER BY fl.fluor_code) AS fluors
  FROM public.plasmids p
  LEFT JOIN public.join_plasmid_fusions jpf
         ON jpf.plasmid_id = p.id
  LEFT JOIN public.fusions f
         ON f.id = jpf.fusion_id
  LEFT JOIN public.fluors fl
         ON fl.id = f.fluor_id
  GROUP BY p.id
)
SELECT
  p.code,
  p.name,
  p.nickname,
  CASE
    WHEN p.nickname IS NULL OR btrim(p.nickname) = '' THEN false
    WHEN btrim(p.nickname) = btrim(p.code)          THEN false
    ELSE true
  END AS has_descriptive_nickname,
  COALESCE(fr.n_fusions, 0) AS n_fusions,
  COALESCE(fr.fluors, '')  AS fluors,
  (COALESCE(fr.n_fusions, 0) = 0) AS missing_fusions,
  (COALESCE(fr.fluors, '') = '')  AS missing_fluors
FROM public.plasmids p
LEFT JOIN fusion_rollup fr
       ON fr.plasmid_id = p.id
ORDER BY p.code;

COMMIT;
