BEGIN;

CREATE OR REPLACE VIEW public.v_fish_groups_overview AS
SELECT
  fg.id::text AS fish_group_id,
  fg.group_code,
  fg.genotype_key,          -- basecode-only genotype (group_key)
  COUNT(DISTINCT fl.id) AS n_lines,
  COUNT(DISTINCT fi.id) AS n_instances,
  MIN(fi.birthday) AS first_birthday,
  MAX(fi.birthday) AS last_birthday,
  -- fluor::tag(tag_pos) summary, e.g. "tdmSG::2xLynk(N) + mChilada::h2b(C)"
  string_agg(
    DISTINCT
      COALESCE(c.fluor_code, '') ||
      CASE
        WHEN COALESCE(c.tag_code, '') <> ''
        THEN '::' || c.tag_code ||
             CASE
               WHEN COALESCE(c.tag_pos, '') <> '' THEN '(' || c.tag_pos || ')'
               ELSE ''
             END
        ELSE ''
      END,
    ' + '
  ) AS fluor_tag,
  -- organelle-fluor summary, e.g. "LAMP1-tdmSG + sec61b-mStayGold"
  string_agg(
    DISTINCT c.tag_code || '-' || COALESCE(c.fluor_code, ''),
    ' + '
  ) FILTER (WHERE COALESCE(c.tag_code, '') <> '') AS organelle_fluor
FROM public.fish_groups fg
LEFT JOIN public.fish_lines fl
  ON fl.fish_group_id = fg.id
LEFT JOIN public.fish_instances_v10 fi
  ON fi.line_id = fl.id
LEFT JOIN public.join_fish_group_alleles jga
  ON jga.fish_group_id = fg.id
LEFT JOIN public.constructs c
  ON c.id = jga.construct_id
GROUP BY fg.id, fg.group_code, fg.genotype_key
ORDER BY fg.group_code;

COMMIT;
