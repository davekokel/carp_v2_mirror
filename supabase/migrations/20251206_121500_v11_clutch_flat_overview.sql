BEGIN;

DROP VIEW IF EXISTS public.v11_clutch_flat_overview;

CREATE VIEW public.v11_clutch_flat_overview AS
WITH base AS (
  SELECT
    cls.clutch_kind          AS level,
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
    cls.label_tg_style             AS transgene_label,
    cls.label_fluortag_style       AS fluor_tag_label,
    cls.label_fluororganelle_style AS organelle_fluor_label
  FROM public.v11_clutch_label_star cls
)
SELECT
  b.level,
  b.clutch_id,
  b.treated_clutch_id,
  b.selection_event_id,
  b.clutch_code,
  b.clutch_date,
  cr.cross_run_code AS cross_code,
  cr.cross_date,
  tp.tank_pair_code,
  COALESCE(mom.fish_code, '') || ' × ' || COALESCE(dad.fish_code, '') AS parent_cross_pretty,
  b.treated_clutch_code,
  b.treatment_code,
  b.treat_text,
  b.selection_label,
  b.genotype_v11_id,
  b.genotype_code,
  b.genotype_basecodes,
  b.genotype_pretty,
  b.transgene_label,
  b.fluor_tag_label,
  b.organelle_fluor_label
FROM base b
LEFT JOIN public.clutches c
  ON c.id = b.clutch_id
LEFT JOIN public.crosses cr
  ON cr.id = c.cross_id
LEFT JOIN public.tank_pairs tp
  ON tp.id = cr.tank_pair_id
LEFT JOIN public.fish_instances_v10 mom
  ON mom.id = cr.female_fish_id
LEFT JOIN public.fish_instances_v10 dad
  ON dad.id = cr.male_fish_id
ORDER BY b.clutch_date DESC NULLS LAST, b.clutch_code, b.level;

COMMIT;
