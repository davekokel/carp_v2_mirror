BEGIN;

DROP VIEW IF EXISTS public.v11_clutch_flat_overview;

CREATE VIEW public.v11_clutch_flat_overview AS
WITH base AS (
  SELECT
    cls.clutch_kind                   AS level,
    cls.clutch_id,
    cls.treated_clutch_id,
    cls.selection_event_id,
    cls.clutch_code,
    cls.clutch_date,
    cls.treated_clutch_code,
    cls.treatment_code,
    cls.treat_text,
    cls.selection_label,
    cls.genotype_v11_id,
    cls.genotype_code,
    cls.genotype_basecodes,
    cls.genotype_pretty,
    cls.genotype_tg_style,
    cls.genotype_fluortag_style,
    cls.genotype_fluororganelle_style,
    cls.label_tg_style,
    cls.label_fluortag_style,
    cls.label_fluororganelle_style
  FROM public.v11_clutch_label_star cls
),
flat AS (
  SELECT
    b.level,
    b.clutch_id,
    b.treated_clutch_id,
    b.selection_event_id,
    b.clutch_code,
    b.clutch_date,
    b.treated_clutch_code,
    b.treatment_code,
    b.treat_text,
    b.selection_label,
    b.genotype_v11_id,
    b.genotype_code,
    b.genotype_basecodes,
    b.genotype_pretty,
    -- existing label fields (kept for compatibility)
    b.label_tg_style              AS transgene_label,
    b.label_fluortag_style        AS fluor_tag_label,
    b.label_fluororganelle_style  AS organelle_fluor_label,
    -- treatment-side rollups
    tls.genotype_basecode_code    AS treatment_basecodes,
    tls.fluor_tag_style           AS treatment_fluor_tag_style,
    tls.fluor_organelle_style     AS treatment_organelle_style,
    -- genotype-side rollups
    b.genotype_fluortag_style,
    b.genotype_fluororganelle_style
  FROM base b
  LEFT JOIN public.v11_treatment_label_star tls
    ON tls.treat_code = b.treatment_code
)
SELECT
  f.level,
  f.clutch_id,
  f.treated_clutch_id,
  f.selection_event_id,
  f.clutch_code,
  f.clutch_date,
  cr.cross_run_code AS cross_code,
  cr.cross_date,
  tp.tank_pair_code,
  (COALESCE(mom.fish_code, ''::text) || ' × '::text || COALESCE(dad.fish_code, ''::text)) AS parent_cross_pretty,
  f.treated_clutch_code,
  f.treatment_code,
  f.treat_text,
  f.selection_label,
  f.genotype_v11_id,
  f.genotype_code,
  f.genotype_basecodes,
  f.genotype_pretty,
  f.transgene_label,
  f.fluor_tag_label,
  f.organelle_fluor_label,

  -- 1. Basecode style: treatment basecodes (mgco-*) > genotype basecodes (pDQM*, etc.)
  CASE
    WHEN COALESCE(f.treatment_basecodes, ''::text) <> ''::text
         AND COALESCE(f.genotype_basecodes, ''::text) <> ''::text
      THEN f.treatment_basecodes || ' > '::text || f.genotype_basecodes
    WHEN COALESCE(f.treatment_basecodes, ''::text) <> ''::text
      THEN f.treatment_basecodes
    ELSE COALESCE(f.genotype_basecodes, ''::text)
  END AS marker_basecode_style,

  -- 2. Fluor-tag style: treatment fluor-tag > genotype fluor-tag
  CASE
    WHEN COALESCE(f.treatment_fluor_tag_style, ''::text) <> ''::text
         AND COALESCE(f.genotype_fluortag_style, ''::text) <> ''::text
      THEN f.treatment_fluor_tag_style || ' > '::text || f.genotype_fluortag_style
    WHEN COALESCE(f.treatment_fluor_tag_style, ''::text) <> ''::text
      THEN f.treatment_fluor_tag_style
    ELSE COALESCE(f.genotype_fluortag_style, ''::text)
  END AS marker_fluortag_style,

  -- 3. Organelle–fluor style: treatment organelle > genotype organelle
  CASE
    WHEN COALESCE(f.treatment_organelle_style, ''::text) <> ''::text
         AND COALESCE(f.genotype_fluororganelle_style, ''::text) <> ''::text
      THEN f.treatment_organelle_style || ' > '::text || f.genotype_fluororganelle_style
    WHEN COALESCE(f.treatment_organelle_style, ''::text) <> ''::text
      THEN f.treatment_organelle_style
    ELSE COALESCE(f.genotype_fluororganelle_style, ''::text)
  END AS marker_organelle_style

FROM flat f
LEFT JOIN public.clutches c              ON c.id = f.clutch_id
LEFT JOIN public.crosses cr              ON cr.id = c.cross_id
LEFT JOIN public.tank_pairs tp           ON tp.id = cr.tank_pair_id
LEFT JOIN public.fish_instances_v10 mom  ON mom.id = cr.female_fish_id
LEFT JOIN public.fish_instances_v10 dad  ON dad.id = cr.male_fish_id
ORDER BY f.clutch_date DESC NULLS LAST,
         f.clutch_code,
         f.level;

COMMIT;
