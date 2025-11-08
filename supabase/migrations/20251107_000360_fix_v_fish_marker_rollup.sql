BEGIN;

-- Rebuild marker rollup on top of fish -> join_fish_fluorescent_treatments -> ft_proteins/ft_dyes
DROP VIEW IF EXISTS public.v_fish_marker_rollup_by_ids;

CREATE VIEW public.v_fish_marker_rollup_by_ids AS
WITH j AS (
  SELECT f.id AS fish_id, jft.ft_code
  FROM public.fish f
  LEFT JOIN public.join_fish_fluorescent_treatments jft
    ON jft.fish_id = f.id
),
flu AS (
  SELECT j.fish_id, p.fluor_code
  FROM j
  LEFT JOIN public.ft_proteins p
    ON p.ft_code = j.ft_code
),
tag AS (
  SELECT j.fish_id, p.tag_code
  FROM j
  LEFT JOIN public.ft_proteins p
    ON p.ft_code = j.ft_code
),
dye AS (
  SELECT j.fish_id, d.dye_code
  FROM j
  LEFT JOIN public.ft_dyes d
    ON d.ft_code = j.ft_code
)
SELECT
  x.fish_id,
  -- Optional: keep a human markers string; not used by v_fish_overview_id but handy
  COALESCE(
    (SELECT string_agg(DISTINCT ft_code, ',' ORDER BY ft_code) FROM j WHERE j.fish_id = x.fish_id),
    ''
  ) AS markers_rollup,
  COALESCE(
    (SELECT string_agg(DISTINCT fluor_code, ',' ORDER BY fluor_code) FROM flu WHERE flu.fish_id = x.fish_id AND fluor_code IS NOT NULL),
    ''
  ) AS fluor_rollup,
  COALESCE(
    (SELECT string_agg(DISTINCT tag_code, ',' ORDER BY tag_code) FROM tag WHERE tag.fish_id = x.fish_id AND tag_code IS NOT NULL),
    ''
  ) AS tag_rollup,
  COALESCE(
    (SELECT string_agg(DISTINCT dye_code, ',' ORDER BY dye_code) FROM dye WHERE dye.fish_id = x.fish_id AND dye_code IS NOT NULL),
    ''
  ) AS dye_rollup,
  -- Placeholder for now (no direct fusion source in this path)
  ''::text AS fusion_rollup
FROM (
  SELECT id AS fish_id FROM public.fish
) AS x;

COMMIT;
