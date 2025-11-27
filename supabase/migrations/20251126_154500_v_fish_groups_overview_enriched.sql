BEGIN;

DROP VIEW IF EXISTS public.v_fish_groups_overview;

CREATE VIEW public.v_fish_groups_overview AS
SELECT
  fg.id::text AS fish_group_id,
  fg.group_code,
  fg.genotype_key,
  string_agg(
    DISTINCT COALESCE(c.base_code, ''),
    ' + '
  ) FILTER (WHERE COALESCE(c.base_code, '') <> '') AS basecode_genotype,
  COUNT(DISTINCT fl.id) AS n_lines,
  COUNT(DISTINCT fi.id) AS n_instances,
  MIN(fi.birthday) AS first_birthday,
  MAX(fi.birthday) AS last_birthday,
  -- fluor::tag(tag_pos) summary from enriched instance view
  string_agg(
    DISTINCT COALESCE(vie.fusion_pretty, ''),
    ' + '
  ) FILTER (WHERE COALESCE(vie.fusion_pretty, '') <> '') AS fluor_tag,
  -- organelle-fluor summary from enriched instance view
  string_agg(
    DISTINCT COALESCE(vie.organelle_fluors, ''),
    ' + '
  ) FILTER (WHERE COALESCE(vie.organelle_fluors, '') <> '') AS organelle_fluor
FROM public.fish_groups fg
LEFT JOIN public.fish_lines fl
  ON fl.fish_group_id = fg.id
LEFT JOIN public.fish_instances_v10 fi
  ON fi.line_id = fl.id
LEFT JOIN public.v10_fish_instances_overview_enriched vie
  ON vie.fish_instance_id = fi.id
LEFT JOIN public.join_fish_group_alleles jga
  ON jga.fish_group_id = fg.id
LEFT JOIN public.constructs c
  ON c.id = jga.construct_id
GROUP BY fg.id, fg.group_code, fg.genotype_key
ORDER BY fg.group_code;

COMMIT;
