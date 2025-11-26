BEGIN;

DROP VIEW IF EXISTS public.v10_constructs_overview;

CREATE VIEW public.v10_constructs_overview AS
SELECT
  c.construct_code,
  c.construct_kind,
  c.construct_name,
  c.resistance,
  c.description,
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
  ) AS organelle_fluors,
  c.created_at
FROM public.constructs c
LEFT JOIN public.construct_fusions cf ON cf.construct_id = c.id
LEFT JOIN public.fusions f           ON f.id  = cf.fusion_id
LEFT JOIN public.fluors fl           ON fl.id = f.fluor_id
LEFT JOIN public.tags tg             ON tg.id = f.tag_id
GROUP BY
  c.construct_code,
  c.construct_kind,
  c.construct_name,
  c.resistance,
  c.description,
  c.created_at;

COMMIT;
