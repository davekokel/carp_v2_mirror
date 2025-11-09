BEGIN;

-- Keep exact column names & order:
-- fish_id, marker_count (integer), fusion_rollup (text), fluor_rollup (text), tag_rollup (text), dye_rollup (text)
CREATE OR REPLACE VIEW public.v_fish_marker_rollup_by_ids AS
WITH j AS (
  SELECT f.id AS fish_id, jft.ft_code
  FROM public.fish f
  LEFT JOIN public.join_fish_fluorescent_treatments jft ON jft.fish_id = f.id
)
SELECT
  x.fish_id,

  -- marker_count stays INTEGER
  COALESCE((
    SELECT COUNT(DISTINCT j.ft_code)::integer
    FROM j
    WHERE j.fish_id = x.fish_id
  ), 0)::integer AS marker_count,

  -- keep fusion_rollup column; leave empty for now
  ''::text AS fusion_rollup,

  -- fluor_rollup: distinct fluor codes via FT
  COALESCE((
    SELECT string_agg(DISTINCT p.fluor_code, ',' ORDER BY p.fluor_code)
    FROM j
    LEFT JOIN public.ft_proteins p ON p.ft_code = j.ft_code
    WHERE j.fish_id = x.fish_id AND p.fluor_code IS NOT NULL
  ), '')::text AS fluor_rollup,

  -- tag_rollup: distinct tag codes via FT
  COALESCE((
    SELECT string_agg(DISTINCT p.tag_code, ',' ORDER BY p.tag_code)
    FROM j
    LEFT JOIN public.ft_proteins p ON p.ft_code = j.ft_code
    WHERE j.fish_id = x.fish_id AND p.tag_code IS NOT NULL
  ), '')::text AS tag_rollup,

  -- dye_rollup: distinct dye codes via FT
  COALESCE((
    SELECT string_agg(DISTINCT d.dye_code, ',' ORDER BY d.dye_code)
    FROM j
    LEFT JOIN public.ft_dyes d ON d.ft_code = j.ft_code
    WHERE j.fish_id = x.fish_id AND d.dye_code IS NOT NULL
  ), '')::text AS dye_rollup

FROM (SELECT id AS fish_id FROM public.fish) AS x;

COMMIT;
