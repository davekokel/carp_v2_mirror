BEGIN;

-- Preserve existing column shape:
-- fish_id (uuid?), marker_count (integer), fluor_rollup (text), tag_rollup (text), dye_rollup (text), fusion_rollup (text)
CREATE OR REPLACE VIEW public.v_fish_marker_rollup_by_ids AS
WITH j AS (
  SELECT f.id AS fish_id, jft.ft_code
  FROM public.fish f
  LEFT JOIN public.join_fish_fluorescent_treatments jft
    ON jft.fish_id = f.id
)
SELECT
  x.fish_id,
  /* keep marker_count as integer = # distinct FT codes for this fish */
  COALESCE((
    SELECT COUNT(DISTINCT j.ft_code)
    FROM j
    WHERE j.fish_id = x.fish_id
  ), 0) AS marker_count,

  /* Fluors: distinct fluor codes reachable via FT code */
  COALESCE((
    SELECT string_agg(DISTINCT p.fluor_code, ',' ORDER BY p.fluor_code)
    FROM j
    LEFT JOIN public.ft_proteins p ON p.ft_code = j.ft_code
    WHERE j.fish_id = x.fish_id AND p.fluor_code IS NOT NULL
  ), '') AS fluor_rollup,

  /* Tags: distinct tag codes reachable via FT code */
  COALESCE((
    SELECT string_agg(DISTINCT p.tag_code, ',' ORDER BY p.tag_code)
    FROM j
    LEFT JOIN public.ft_proteins p ON p.ft_code = j.ft_code
    WHERE j.fish_id = x.fish_id AND p.tag_code IS NOT NULL
  ), '') AS tag_rollup,

  /* Dyes: distinct dye codes reachable via FT code */
  COALESCE((
    SELECT string_agg(DISTINCT d.dye_code, ',' ORDER BY d.dye_code)
    FROM j
    LEFT JOIN public.ft_dyes d ON d.ft_code = j.ft_code
    WHERE j.fish_id = x.fish_id AND d.dye_code IS NOT NULL
  ), '') AS dye_rollup,

  /* Not wired yet; keep as empty text to preserve shape expected by v_fish_overview_id */
  ''::text AS fusion_rollup
FROM (SELECT id AS fish_id FROM public.fish) AS x;

COMMIT;
