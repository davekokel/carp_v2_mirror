BEGIN;
DROP VIEW IF EXISTS public.v_rnas;
CREATE VIEW public.v_rnas AS
WITH rp AS (
  SELECT
    r.id AS rna_id,
    fu.fusion_name
  FROM public.rnas r
  JOIN public.rna_proteins rp
    ON rp.rna_code = r.rna_code
  LEFT JOIN public.fluors fl
    ON fl.fluor_code = rp.fluor_code
  LEFT JOIN public.tags tg
    ON tg.tag_code = rp.tag_code
  LEFT JOIN public.fusions fu
    ON fu.fluor_id = fl.id
   AND fu.tag_id  = tg.id
  WHERE NULLIF(COALESCE(fu.fusion_name,''),'') IS NOT NULL
)
SELECT
  r.id AS rna_id,
  r.rna_code,
  r.rna_name,
  COALESCE((
    SELECT string_agg(s.fusion_name, ', ' ORDER BY s.fusion_name)
    FROM (SELECT DISTINCT fusion_name FROM rp WHERE rp.rna_id = r.id) AS s
  ), '') AS fusion_names
FROM public.rnas r;
COMMIT;
