BEGIN;

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

DROP VIEW IF EXISTS public.v11_fish_instance_star_labels CASCADE;

CREATE VIEW public.v11_fish_instance_star_labels AS
SELECT
  fis.*,
  COALESCE(fls_lbl.genotype_tg_style, fis.genotype_pretty) AS genotype_tg_style,
  COALESCE(fmrn.fluor_tag_rollup, fis.genotype_pretty) AS genotype_fluortag_style,
  COALESCE(fmrn.organelle_fluor_rollup, fis.genotype_pretty) AS genotype_fluororganelle_style
FROM public.v11_fish_instance_star fis
LEFT JOIN public.v11_fish_line_star_labels fls_lbl
  ON fls_lbl.line_code = fis.line_code
LEFT JOIN public.v11_fish_marker_rollups_nice fmrn
  ON fmrn.fish_instance_id = fis.fish_instance_id;

COMMIT;
