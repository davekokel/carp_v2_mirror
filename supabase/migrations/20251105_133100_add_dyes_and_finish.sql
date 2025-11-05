BEGIN;

CREATE TABLE IF NOT EXISTS public.dyes (
  dye_code text PRIMARY KEY,
  dye_name text
);

CREATE TABLE IF NOT EXISTS public.ft_dye_markers (
  id       bigserial PRIMARY KEY,
  ft_code  text NOT NULL REFERENCES public.fluorescent_treatments(ft_code) ON DELETE CASCADE,
  dye_code text NOT NULL REFERENCES public.dyes(dye_code)
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_ft_dye_marker
  ON public.ft_dye_markers (ft_code, dye_code);

DROP VIEW IF EXISTS public.v_fish_fluorescent_markers;
DROP VIEW IF EXISTS public.v_fluorescent_treatment_markers;

CREATE OR REPLACE VIEW public.v_fluorescent_treatment_markers AS
SELECT
  m.ft_code,
  'fluor_protein_' || CASE WHEN m.tag_code IS NULL THEN 'untagged' ELSE 'tagged' END AS marker_kind,
  m.fluor_code,
  m.tag_code,
  NULL::text AS dye_code,
  CASE WHEN m.tag_code IS NULL THEN m.fluor_code
       ELSE m.tag_code || '::' || m.fluor_code END AS marker_label
FROM public.ft_protein_markers m
UNION ALL
SELECT
  d.ft_code,
  'dye' AS marker_kind,
  NULL::text AS fluor_code,
  NULL::text AS tag_code,
  d.dye_code,
  d.dye_code AS marker_label
FROM public.ft_dye_markers d;

CREATE OR REPLACE VIEW public.v_fish_fluorescent_markers AS
SELECT
  f.id AS fish_id,
  f.fish_code,
  array_remove(array_agg(DISTINCT v.marker_label ORDER BY v.marker_label), NULL) AS markers,
  array_remove(array_agg(DISTINCT v.fluor_code   ORDER BY v.fluor_code),   NULL) AS fluors,
  array_remove(array_agg(DISTINCT v.tag_code     ORDER BY v.tag_code),     NULL) AS tags,
  array_remove(array_agg(DISTINCT v.dye_code     ORDER BY v.dye_code),     NULL) AS dyes
FROM public.join_fish_fluorescent_treatments j
JOIN public.fish f ON f.id = j.fish_id
LEFT JOIN public.v_fluorescent_treatment_markers v ON v.ft_code = j.ft_code
GROUP BY f.id, f.fish_code;

COMMIT;
