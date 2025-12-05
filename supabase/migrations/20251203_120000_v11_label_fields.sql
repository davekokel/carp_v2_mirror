BEGIN;

CREATE OR REPLACE FUNCTION public.render_cross_label(
  left_genotype  text,
  right_genotype text
)
RETURNS text
LANGUAGE sql
IMMUTABLE
AS $$
  SELECT CASE
    WHEN left_genotype IS NULL AND right_genotype IS NULL THEN NULL
    WHEN left_genotype IS NULL THEN right_genotype
    WHEN right_genotype IS NULL THEN left_genotype
    ELSE left_genotype || ' × ' || right_genotype
  END;
$$;

CREATE OR REPLACE FUNCTION public.render_treatment_label(
  treatment_pretty text,
  genotype_pretty  text
)
RETURNS text
LANGUAGE sql
IMMUTABLE
AS $$
  SELECT CASE
    WHEN treatment_pretty IS NULL AND genotype_pretty IS NULL THEN NULL
    WHEN treatment_pretty IS NULL THEN genotype_pretty
    WHEN genotype_pretty IS NULL THEN treatment_pretty
    ELSE treatment_pretty || ' > ' || genotype_pretty
  END;
$$;

DROP VIEW IF EXISTS public.v11_fish_instance_star_labels CASCADE;

CREATE VIEW public.v11_fish_instance_star_labels AS
SELECT
  fis.*,
  COALESCE(far.allele_label_rollup, fis.genotype_pretty) AS genotype_tg_style,
  COALESCE(fmrn.fluor_tag_rollup, fis.genotype_pretty) AS genotype_fluortag_style,
  COALESCE(fmrn.organelle_fluor_rollup, fis.genotype_pretty) AS genotype_fluororganelle_style
FROM public.v11_fish_instance_star fis
LEFT JOIN public.v11_fish_allele_rollups far
  ON far.fish_instance_id = fis.fish_instance_id
LEFT JOIN public.v11_fish_marker_rollups_nice fmrn
  ON fmrn.fish_instance_id = fis.fish_instance_id;

DROP VIEW IF EXISTS public.v11_fish_line_star_labels CASCADE;

CREATE VIEW public.v11_fish_line_star_labels AS
SELECT
  fls.*,
  COALESCE(lar.allele_label_rollup, fls.genotype_pretty) AS genotype_tg_style,
  fls.genotype_pretty AS genotype_fluortag_style,
  fls.genotype_pretty AS genotype_fluororganelle_style
FROM public.v11_fish_line_star fls
LEFT JOIN public.v11_line_allele_rollups lar
  ON lar.line_id = fls.line_id;

DROP VIEW IF EXISTS public.v11_cross_parent_genotypes_labels CASCADE;

CREATE VIEW public.v11_cross_parent_genotypes_labels AS
SELECT
  cpg.*,
  public.render_cross_label(
    cpg.mother_genotype_pretty,
    cpg.father_genotype_pretty
  ) AS cross_label_tg_style,
  public.render_cross_label(
    cpg.mother_genotype_pretty,
    cpg.father_genotype_pretty
  ) AS cross_label_fluortag_style,
  public.render_cross_label(
    cpg.mother_genotype_pretty,
    cpg.father_genotype_pretty
  ) AS cross_label_fluororganelle_style
FROM public.v11_cross_parent_genotypes cpg;

DROP VIEW IF EXISTS public.v11_treated_clutch_genotype_star_labels CASCADE;

CREATE VIEW public.v11_treated_clutch_genotype_star_labels AS
SELECT
  tcgs.*,
  public.render_treatment_label(
    ts.treat_text,
    tcgs.genotype_pretty
  ) AS treatment_label_tg_style,
  public.render_treatment_label(
    ts.all_fluor_tag_rollup,
    tcgs.genotype_pretty
  ) AS treatment_label_fluortag_style,
  public.render_treatment_label(
    ts.all_organelle_fluor_rollup,
    tcgs.genotype_pretty
  ) AS treatment_label_fluororganelle_style
FROM public.v11_treated_clutch_genotype_star tcgs
LEFT JOIN public.treated_clutches_v11 tc
  ON tc.id = tcgs.treated_clutch_id
LEFT JOIN public.v11_treatment_star ts
  ON tc.treatment_id::text = ts.treatment_id;

COMMIT;
