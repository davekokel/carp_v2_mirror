BEGIN;

DROP VIEW IF EXISTS public.v10_fish_instances_overview_enriched;

CREATE VIEW public.v10_fish_instances_overview_enriched AS
SELECT
  o.fish_instance_id,
  o.fish_code,
  o.line_id,
  o.birthday,
  o.fish_notes,
  o.fish_created_at,
  o.line_code,
  o.line_nickname,
  o.genetic_background,
  o.line_building_stage,
  o.line_created_at,
  o.genotype_pretty,
  o.fluor_codes,
  o.tag_codes,
  lf.n_fusions,
  lf.fusion_pretty,
  lf.organelle_fluors
FROM public.v10_fish_instances_overview o
LEFT JOIN (
  SELECT
    fln.id AS line_id,
    COUNT(DISTINCT f.id) AS n_fusions,
    string_agg(
      DISTINCT CASE
        WHEN fl.fluor_code IS NULL THEN NULL
        WHEN tg.tag_code IS NULL AND f.tag_pos IS NULL THEN fl.fluor_code
        WHEN tg.tag_code IS NULL THEN fl.fluor_code || '::(' || f.tag_pos || ')'
        WHEN f.tag_pos IS NULL THEN fl.fluor_code || '::' || tg.tag_code
        ELSE fl.fluor_code || '::' || tg.tag_code || '(' || f.tag_pos || ')'
      END,
      ', '
      ORDER BY CASE
        WHEN fl.fluor_code IS NULL THEN NULL
        WHEN tg.tag_code IS NULL AND f.tag_pos IS NULL THEN fl.fluor_code
        WHEN tg.tag_code IS NULL THEN fl.fluor_code || '::(' || f.tag_pos || ')'
        WHEN f.tag_pos IS NULL THEN fl.fluor_code || '::' || tg.tag_code
        ELSE fl.fluor_code || '::' || tg.tag_code || '(' || f.tag_pos || ')'
      END
    ) AS fusion_pretty,
    string_agg(
      DISTINCT CASE
        WHEN fl.fluor_code IS NULL THEN NULL
        WHEN tg.localization IS NULL THEN 'cytosol-' || fl.fluor_code
        ELSE tg.localization || '-' || fl.fluor_code
      END,
      ', '
      ORDER BY CASE
        WHEN fl.fluor_code IS NULL THEN NULL
        WHEN tg.localization IS NULL THEN 'cytosol-' || fl.fluor_code
        ELSE tg.localization || '-' || fl.fluor_code
      END
    ) AS organelle_fluors
  FROM public.fish_lines fln
  LEFT JOIN public.join_line_alleles jla ON jla.line_id      = fln.id
  LEFT JOIN public.construct_fusions cf  ON cf.construct_id  = jla.construct_id
  LEFT JOIN public.fusions f             ON f.id             = cf.fusion_id
  LEFT JOIN public.fluors fl             ON fl.id            = f.fluor_id
  LEFT JOIN public.tags tg               ON tg.id            = f.tag_id
  GROUP BY fln.id
) lf ON lf.line_id = o.line_id;

COMMIT;
