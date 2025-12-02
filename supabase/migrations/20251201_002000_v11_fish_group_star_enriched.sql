BEGIN;

DROP VIEW IF EXISTS public.v11_fish_group_star;

CREATE VIEW public.v11_fish_group_star AS
WITH lines AS (
  SELECT
    fl.id::uuid              AS line_id,
    fl.line_code::text       AS line_code,
    fl.nickname::text        AS line_nickname,
    COALESCE(fl.genetic_background,'')::text AS genetic_background,
    fl.construct_code::text  AS line_transgene_rollup
  FROM public.fish_lines fl
),
line_instances AS (
  SELECT
    fi.line_id,
    COUNT(*)::int AS n_instances
  FROM public.fish_instances_v10 fi
  GROUP BY fi.line_id
),
marker_line AS (
  SELECT
    fi.line_id,
    COUNT(DISTINCT mr.fish_instance_id)::int         AS n_marker_fish,
    MAX(mr.n_constructs)::int                        AS line_n_constructs,
    MAX(mr.n_fluors)::int                            AS line_n_fluors,
    COALESCE(
      string_agg(DISTINCT NULLIF(mr.fluor_tag_rollup,''), '||'),
      ''
    ) AS line_fluor_tag_rollup,
    COALESCE(
      string_agg(DISTINCT NULLIF(mr.organelle_fluor_rollup,''), '||'),
      ''
    ) AS line_organelle_fluor_rollup
  FROM public.v11_fish_marker_rollups mr
  JOIN public.fish_instances_v10 fi
    ON fi.id = mr.fish_instance_id
  GROUP BY fi.line_id
),
per_line AS (
  SELECT
    l.line_transgene_rollup,
    l.line_code,
    l.line_nickname,
    l.genetic_background,
    COALESCE(li.n_instances,0)            AS line_n_instances,
    COALESCE(ml.line_fluor_tag_rollup,'') AS line_fluor_tag_rollup,
    COALESCE(ml.line_organelle_fluor_rollup,'') AS line_organelle_fluor_rollup
  FROM lines l
  LEFT JOIN line_instances li ON li.line_id = l.line_id
  LEFT JOIN marker_line    ml ON ml.line_id = l.line_id
  WHERE l.line_transgene_rollup IS NOT NULL
    AND l.line_transgene_rollup <> ''
)
SELECT
  line_transgene_rollup                             AS group_transgene_rollup,
  string_agg(DISTINCT line_code, '||' ORDER BY line_code)            AS group_line_codes,
  string_agg(DISTINCT line_nickname, '||' ORDER BY line_nickname)    AS group_line_nicknames,
  string_agg(DISTINCT genetic_background, '||' ORDER BY genetic_background) AS group_genetic_backgrounds,
  COUNT(DISTINCT line_code)::int                    AS n_lines,
  SUM(line_n_instances)::int                        AS n_instances,
  COALESCE(
    string_agg(DISTINCT NULLIF(line_fluor_tag_rollup,''), '||'),
    ''
  ) AS all_fluor_tag_rollup,
  COALESCE(
    string_agg(DISTINCT NULLIF(line_organelle_fluor_rollup,''), '||'),
    ''
  ) AS all_organelle_fluor_rollup
FROM per_line
GROUP BY line_transgene_rollup;

COMMENT ON VIEW public.v11_fish_group_star IS
  'v11 fish group star: groups of lines sharing the same construct base_code, with line counts, instance counts, and marker rollups.';

COMMIT;
