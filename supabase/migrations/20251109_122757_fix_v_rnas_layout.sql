BEGIN;

DROP VIEW IF EXISTS public.v_rnas CASCADE;

CREATE VIEW public.v_rnas AS
WITH jf AS (
  SELECT
    j.rna_id,
    f.id AS fusion_id,
    fl.fluor_code,
    tg.tag_code
  FROM public.join_rna_fusions j
  JOIN public.fusions f ON f.id=j.fusion_id
  JOIN public.fluors fl ON fl.id=f.fluor_id
  LEFT JOIN public.tags tg ON tg.id=f.tag_id
),
agg AS (
  SELECT
    rna_id,
    (
      SELECT string_agg(s.fluor_code, ', ' ORDER BY s.fluor_code)
      FROM (SELECT DISTINCT fluor_code FROM jf x WHERE x.rna_id=jf.rna_id) s
    ) AS fluors,
    (
      SELECT COALESCE(string_agg(s.tag_code, ', ' ORDER BY s.tag_code),'')
      FROM (SELECT DISTINCT tag_code FROM jf x WHERE x.rna_id=jf.rna_id AND x.tag_code IS NOT NULL) s
    ) AS tags
  FROM jf
  GROUP BY rna_id
)
SELECT
  r.rna_code,
  r.nickname,
  r.notes,
  COALESCE(agg.fluors,'') AS fluors,
  COALESCE(agg.tags,'')   AS tags,
  r.created_at
FROM public.rnas r
LEFT JOIN agg ON agg.rna_id=r.id;

COMMIT;
