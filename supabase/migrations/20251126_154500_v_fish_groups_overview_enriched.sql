BEGIN;

DROP VIEW IF EXISTS public.v_fish_groups_overview;

CREATE VIEW public.v_fish_groups_overview AS
SELECT
  fg.id::text AS fish_group_id,
  fg.group_code,
  fg.genotype_key,
  -- basecode genotype (construct base_codes)
  string_agg(
    DISTINCT COALESCE(c.base_code, ''),
    ' + '
  ) FILTER (WHERE COALESCE(c.base_code, '') <> '') AS basecode_genotype,
  COUNT(DISTINCT fln.id) AS n_lines,
  COUNT(DISTINCT fi.id)  AS n_instances,
  MIN(fi.birthday)       AS first_birthday,
  MAX(fi.birthday)       AS last_birthday,
  -- fluor::tag(tag_pos), e.g. "tdmSG::2xLynk(N)"
  string_agg(
    DISTINCT
      COALESCE(fl.fluor_code, '') ||
      CASE
        WHEN tg.tag_code IS NOT NULL AND tg.tag_code <> '' THEN
          '::' || tg.tag_code ||
          CASE
            WHEN f.tag_pos IS NOT NULL AND f.tag_pos <> '' THEN
              '(' || f.tag_pos || ')'
            ELSE ''
          END
        ELSE ''
      END,
    ' + '
  ) FILTER (WHERE fl.fluor_code IS NOT NULL) AS fluor_tag,
  -- organelle-fluor, e.g. "membrane-tdmSG"
  string_agg(
    DISTINCT
      COALESCE(tg.localization, '') ||
      CASE
        WHEN fl.fluor_code IS NOT NULL THEN
          '-' || fl.fluor_code
        ELSE ''
      END,
    ' + '
  ) FILTER (WHERE tg.localization IS NOT NULL AND tg.localization <> '') AS organelle_fluor
FROM public.fish_groups fg
LEFT JOIN public.fish_lines fln
  ON fln.fish_group_id = fg.id
LEFT JOIN public.fish_instances_v10 fi
  ON fi.line_id = fln.id
LEFT JOIN public.join_fish_group_alleles jga
  ON jga.fish_group_id = fg.id
LEFT JOIN public.constructs c
  ON c.id = jga.construct_id
LEFT JOIN public.construct_fusions cf
  ON cf.construct_id = c.id
LEFT JOIN public.fusions f
  ON f.id = cf.fusion_id
LEFT JOIN public.fluors fl
  ON fl.id = f.fluor_id
LEFT JOIN public.tags tg
  ON tg.id = f.tag_id
GROUP BY
  fg.id,
  fg.group_code,
  fg.genotype_key
ORDER BY
  fg.group_code;

COMMIT;
