BEGIN;

DROP VIEW IF EXISTS public.v11_fish_instance_star_labels;

CREATE VIEW public.v11_fish_instance_star_labels AS
WITH base AS (
  SELECT
    fis.fish_instance_id,
    fis.fish_code,
    fis.birthday,
    fis.instance_stage,
    fis.line_code,
    fis.line_nickname,
    fis.genetic_background,
    fis.line_construct_code,
    fis.allele_canonical_rollup,
    fis.allele_label_rollup,
    fis.genotype_basecodes,
    fis.genotype_v11_id,
    fis.genotype_code,
    fis.genotype_pretty,
    COALESCE(fls_lbl.genotype_tg_style,       fis.genotype_pretty) AS genotype_tg_style,
    COALESCE(fmrn.fluor_tag_rollup,           fis.genotype_pretty) AS genotype_fluortag_style,
    COALESCE(fmrn.organelle_fluor_rollup,     fis.genotype_pretty) AS genotype_fluororganelle_style
  FROM public.v11_fish_instance_star fis
  LEFT JOIN public.v11_fish_line_star_labels fls_lbl
    ON fls_lbl.line_code = fis.line_code
  LEFT JOIN public.v11_fish_marker_rollups_nice fmrn
    ON fmrn.fish_instance_id = fis.fish_instance_id
),
treat_rollups AS (
  SELECT
    jft.fish_instance_id::text AS fish_instance_id,
    string_agg(
      DISTINCT t.treat_code,
      ' || ' ORDER BY t.treat_code
    ) AS treatment_codes,
    string_agg(
      DISTINCT NULLIF(tls.treatment_display, ''),
      ' || ' ORDER BY tls.treatment_display
    ) AS treatment_label_tg_style,
    string_agg(
      DISTINCT NULLIF(tls.fluor_tag_style, ''),
      ' || ' ORDER BY tls.fluor_tag_style
    ) AS treatment_label_fluortag_style,
    string_agg(
      DISTINCT NULLIF(tls.fluor_organelle_style, ''),
      ' || ' ORDER BY tls.fluor_organelle_style
    ) AS treatment_label_fluororganelle_style
  FROM public.join_fish_treatments jft
  JOIN public.treatments t
    ON t.id = jft.treatment_id
  LEFT JOIN public.v11_treatment_label_star tls
    ON tls.treat_code = t.treat_code
  GROUP BY jft.fish_instance_id
)
SELECT
  b.*,
  COALESCE(tr.treatment_codes, '')                  AS treatment_codes,
  COALESCE(tr.treatment_label_tg_style, '')         AS treatment_label_tg_style,
  COALESCE(tr.treatment_label_fluortag_style, '')   AS treatment_label_fluortag_style,
  COALESCE(tr.treatment_label_fluororganelle_style, '') AS treatment_label_fluororganelle_style
FROM base b
LEFT JOIN treat_rollups tr
  ON tr.fish_instance_id = b.fish_instance_id;

COMMENT ON VIEW public.v11_fish_instance_star_labels IS
'v11 fish instance star view with genotype labels and per-instance treatment label rollups.';

COMMIT;
