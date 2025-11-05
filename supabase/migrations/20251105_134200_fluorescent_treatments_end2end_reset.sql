BEGIN;

DROP VIEW IF EXISTS public.v_fish_fluorescent_markers;
DROP VIEW IF EXISTS public.v_fluorescent_treatment_markers;

DROP TABLE IF EXISTS public.ft_injection_mix_sources;
DROP TABLE IF EXISTS public.ft_injection_mixes;
DROP TABLE IF EXISTS public.ft_protein_markers;
DROP TABLE IF EXISTS public.ft_dye_markers;
DROP TABLE IF EXISTS public.join_fish_fluorescent_treatments;
DROP TABLE IF EXISTS public.fluorescent_treatments;
DROP TABLE IF EXISTS public.dyes;

CREATE TABLE public.fluorescent_treatments (
  ft_code    text PRIMARY KEY,
  ft_text    text NOT NULL,
  ft_meta    jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  created_by text
);

CREATE TABLE public.ft_injection_mixes (
  ft_code       text PRIMARY KEY REFERENCES public.fluorescent_treatments(ft_code) ON DELETE CASCADE,
  protocol_code text,
  protocol_text text,
  notes         text
);

CREATE TABLE public.ft_injection_mix_sources (
  id          bigserial PRIMARY KEY,
  ft_code     text NOT NULL REFERENCES public.fluorescent_treatments(ft_code) ON DELETE CASCADE,
  source_kind text NOT NULL CHECK (source_kind IN ('plasmid','enzyme','oligo','pcr_product','mrna','grna','protocol','other')),
  ref_code    text,
  ref_text    text,
  qty         numeric,
  units       text,
  role        text,
  notes       jsonb,
  CONSTRAINT ck_ftmix_src_ref_present CHECK (ref_code IS NOT NULL OR ref_text IS NOT NULL)
);
CREATE UNIQUE INDEX uq_ftmix_src ON public.ft_injection_mix_sources (ft_code, source_kind, COALESCE(ref_code,'∅'), COALESCE(ref_text,'∅'));

CREATE TABLE public.fluors (fluor_code text PRIMARY KEY) ;
CREATE TABLE public.tags   (tag_code   text PRIMARY KEY) ;
CREATE TABLE public.dyes   (dye_code   text PRIMARY KEY, dye_name text);

CREATE TABLE public.ft_protein_markers (
  id         bigserial PRIMARY KEY,
  ft_code    text NOT NULL REFERENCES public.fluorescent_treatments(ft_code) ON DELETE CASCADE,
  fluor_code text NOT NULL REFERENCES public.fluors(fluor_code),
  tag_code   text REFERENCES public.tags(tag_code)
);
CREATE UNIQUE INDEX uq_ft_protein_marker ON public.ft_protein_markers (ft_code, COALESCE(tag_code,'∅'), fluor_code);

CREATE TABLE public.ft_dye_markers (
  id       bigserial PRIMARY KEY,
  ft_code  text NOT NULL REFERENCES public.fluorescent_treatments(ft_code) ON DELETE CASCADE,
  dye_code text NOT NULL REFERENCES public.dyes(dye_code)
);
CREATE UNIQUE INDEX uq_ft_dye_marker ON public.ft_dye_markers (ft_code, dye_code);

CREATE TABLE public.join_fish_fluorescent_treatments (
  fish_id  uuid NOT NULL REFERENCES public.fish(id) ON DELETE CASCADE,
  ft_code  text NOT NULL REFERENCES public.fluorescent_treatments(ft_code) ON DELETE RESTRICT,
  allele_number text,
  zygosity text,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (fish_id, ft_code)
);

CREATE OR REPLACE VIEW public.v_fluorescent_treatment_markers AS
SELECT
  m.ft_code,
  'fluor_protein_' || CASE WHEN m.tag_code IS NULL THEN 'untagged' ELSE 'tagged' END AS marker_kind,
  m.fluor_code,
  m.tag_code,
  NULL::text AS dye_code,
  CASE WHEN m.tag_code IS NULL THEN m.fluor_code ELSE m.tag_code || '::' || m.fluor_code END AS marker_label
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
