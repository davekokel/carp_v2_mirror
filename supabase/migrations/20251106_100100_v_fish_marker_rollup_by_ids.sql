BEGIN;
CREATE OR REPLACE VIEW public.v_fish_marker_rollup_by_ids
(fish_id, marker_count, fusion_rollup, fluor_rollup, tag_rollup, dye_rollup)
AS
WITH links AS (
  SELECT
    j.fish_id,
    m.fluor_label,
    m.tag_label,
    m.dye_label,
    CASE
      WHEN COALESCE(m.fluor_label,'')<>'' AND COALESCE(m.tag_label,'')<>'' THEN m.fluor_label||'::'||m.tag_label
      WHEN COALESCE(m.fluor_label,'')<>'' THEN m.fluor_label
      WHEN COALESCE(m.dye_label,'')<>''   THEN m.dye_label
      ELSE ''
    END AS fusion_label
  FROM public.join_fish_fluorescent_treatments j
  JOIN public.v_fluorescent_treatment_markers m
    ON m.ft_code = j.ft_code
)
SELECT
  fish_id,
  COUNT(*)::int AS marker_count,
  COALESCE(NULLIF(string_agg(DISTINCT fusion_label, ', '),''),'') AS fusion_label,
  COALESCE(NULLIF(string_agg(DISTINCT COALESCE(fluor_label,''), ', '),''),'') AS fluor_label,
  COALESCE(NULLIF(string_agg(DISTINCT COALESCE(tag_label,''),   ', '),''),'') AS tag_label,
  COALESCE(NULLIF(string_agg(DISTINCT COALESCE(dye_label,''),   ', '),''),'') AS dye_label
FROM links
GROUP BY fish_id;
COMMIT;
