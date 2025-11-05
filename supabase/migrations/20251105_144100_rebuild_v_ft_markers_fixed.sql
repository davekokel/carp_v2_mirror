BEGIN;

DROP VIEW IF EXISTS public.v_fish_fluorescent_markers;
DROP VIEW IF EXISTS public.v_fluorescent_treatment_markers;

CREATE VIEW public.v_fluorescent_treatment_markers AS
SELECT
  p.ft_code,
  'protein'::text AS marker_kind,
  p.fluor_code,
  p.tag_code,
  NULL::text AS dye_code,
  vf.label AS fluor_label,
  vt.label AS tag_label,
  NULL::text AS dye_label,
  COALESCE(vt.label, vf.label) AS marker_label,
  p.created_at
FROM public.ft_proteins p
LEFT JOIN public.v_fluors_lu vf ON vf.code = p.fluor_code
LEFT JOIN public.v_tags_lu   vt ON vt.code = p.tag_code
UNION ALL
SELECT
  d.ft_code,
  'dye'::text AS marker_kind,
  NULL::text AS fluor_code,
  NULL::text AS tag_code,
  d.dye_code,
  NULL::text AS fluor_label,
  NULL::text AS tag_label,
  vd.label AS dye_label,
  vd.label AS marker_label,
  d.created_at
FROM public.ft_dyes d
LEFT JOIN public.v_dyes_lu vd ON vd.code = d.dye_code
;

CREATE VIEW public.v_fish_fluorescent_markers AS
SELECT
  f.id::text AS fish_pk,
  f.fish_code::text AS fish_code,
  j.fish_id::text AS fish_ref_in_join,
  j.ft_code::text AS ft_code,
  m.marker_kind,
  m.fluor_code,
  m.fluor_label,
  m.tag_code,
  m.tag_label,
  m.dye_code,
  m.dye_label,
  m.marker_label,
  COALESCE(j.created_at, m.created_at) AS linked_at
FROM public.join_fish_fluorescent_treatments j
JOIN public.fish f ON f.id = j.fish_id
JOIN public.v_fluorescent_treatment_markers m ON m.ft_code = j.ft_code;

COMMIT;
