BEGIN;

CREATE OR REPLACE VIEW public.v_construct_marker_styles AS
WITH j AS (
  SELECT
    lower(btrim(c.base_code)) AS base_code,
    NULLIF(btrim(COALESCE(flu.nickname, flu.display_name, flu.code)), '') AS fluor,
    NULLIF(btrim(COALESCE(t.nickname, t.display_name, t.code)), '') AS tag,
    NULLIF(btrim(f.tag_pos), '') AS tag_pos,
    NULLIF(btrim(t.localization), '') AS localization
  FROM public.constructs c
  LEFT JOIN public.construct_fusions cf ON cf.construct_id = c.id
  LEFT JOIN public.fusions f ON f.id = cf.fusion_id
  LEFT JOIN public.fluors flu ON flu.id = f.fluor_id
  LEFT JOIN public.tags t ON t.id = f.tag_id
),
ft_tokens AS (
  SELECT DISTINCT
    j.base_code,
    CASE
      WHEN j.fluor IS NOT NULL AND j.tag IS NOT NULL THEN
        (j.fluor || '-' || j.tag) ||
        CASE WHEN j.tag_pos IS NOT NULL THEN '(' || j.tag_pos || ')' ELSE '' END
      WHEN j.fluor IS NOT NULL THEN j.fluor
      ELSE NULL
    END AS tok
  FROM j
),
fo_tokens AS (
  SELECT DISTINCT
    j.base_code,
    CASE
      WHEN j.fluor IS NOT NULL AND j.localization IS NOT NULL THEN (j.fluor || '-' || j.localization)
      WHEN j.fluor IS NOT NULL THEN j.fluor
      ELSE NULL
    END AS tok
  FROM j
),
ft AS (
  SELECT
    ft_tokens.base_code,
    string_agg(ft_tokens.tok, '; ' ORDER BY ft_tokens.tok) AS fluortag_style
  FROM ft_tokens
  WHERE ft_tokens.tok IS NOT NULL AND btrim(ft_tokens.tok) <> ''
  GROUP BY ft_tokens.base_code
),
fo AS (
  SELECT
    fo_tokens.base_code,
    string_agg(fo_tokens.tok, '; ' ORDER BY fo_tokens.tok) AS fluororganelle_style
  FROM fo_tokens
  WHERE fo_tokens.tok IS NOT NULL AND btrim(fo_tokens.tok) <> ''
  GROUP BY fo_tokens.base_code
)
SELECT
  b.base_code,
  ft.fluortag_style,
  fo.fluororganelle_style
FROM (SELECT DISTINCT j.base_code FROM j) b
LEFT JOIN ft USING (base_code)
LEFT JOIN fo USING (base_code);

COMMIT;
