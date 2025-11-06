BEGIN;

CREATE OR REPLACE VIEW public.v_fish_fluorescent_markers
(fish_code, markers, fluors, tags, dyes)
AS
WITH m AS (
  SELECT
    f.fish_code,
    vm.marker_kind,
    COALESCE(vm.fluor_label,'') AS fluor_label,
    COALESCE(vm.tag_label,''  )  AS tag_label,
    COALESCE(vm.dye_label,''  )  AS dye_label,
    CASE
      WHEN COALESCE(vm.fluor_label,'')<>'' AND COALESCE(vm.tag_label,'')<>'' THEN vm.fluor_label||'::'||vm.tag_label
      WHEN COALESCE(vm.fluor_label,'')<>'' THEN vm.fluor_label
      WHEN COALESCE(vm.dye_label,''  )<>'' THEN vm.dye_label
      ELSE ''
    END AS fusion_label
  FROM public.join_fish_fluorescent_treatments j
  JOIN public.fish f
    ON f.id = j.fish_id
  JOIN public.v_fluorescent_treatment_markers vm
    ON vm.ft_code = j.ft_code
)
SELECT
  fish_code,
  COALESCE(ARRAY_AGG(DISTINCT fusion_label) FILTER (WHERE fusion_label <> ''), ARRAY[]::text[]) AS markers,
  COALESCE(ARRAY_AGG(DISTINCT fluor_label ) FILTER (WHERE fluor_label  <> ''), ARRAY[]::text[]) AS fluors,
  COALESCE(ARRAY_AGG(DISTINCT tag_label   ) FILTER (WHERE tag_label    <> ''), ARRAY[]::text[]) AS tags,
  COALESCE(ARRAY_AGG(DISTINCT dye_label   ) FILTER (WHERE dye_label    <> ''), ARRAY[]::text[]) AS dyes
FROM m
GROUP BY fish_code;

COMMIT;
