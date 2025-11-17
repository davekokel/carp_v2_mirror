BEGIN;

DROP VIEW IF EXISTS public.v_plasmids_overview;

CREATE VIEW public.v_plasmids_overview AS
WITH plasmid_fusions AS (
  SELECT
    p.code,
    p.name,
    p.nickname,
    p.created_at,
    jpf.fusion_id,
    vfl.fusion_label,
    vfl.fluor_code,
    vfl.tag_code
  FROM public.plasmids AS p
  LEFT JOIN public.join_plasmid_fusions AS jpf
    ON jpf.plasmid_id = p.id
  LEFT JOIN public.v_fusion_labels AS vfl
    ON vfl.fusion_id = jpf.fusion_id
)
SELECT
  code,
  name,
  nickname,
  NULL::text AS resistance,
  string_agg(DISTINCT fluor_code, ', ' ORDER BY fluor_code)       AS fluors,
  string_agg(DISTINCT tag_code,   ', ' ORDER BY tag_code)         AS tag_codes,
  string_agg(DISTINCT fusion_label, '; ' ORDER BY fusion_label)   AS fusions,
  COUNT(DISTINCT fusion_id)                                       AS n_fusions,
  MIN(created_at)                                                 AS created_at
FROM plasmid_fusions
GROUP BY
  code,
  name,
  nickname;

COMMIT;
