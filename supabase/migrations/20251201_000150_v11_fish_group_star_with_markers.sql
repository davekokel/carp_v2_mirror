BEGIN;

CREATE OR REPLACE VIEW public.v11_fish_group_star AS
WITH line_core AS (
  SELECT
    ls.line_id,
    ls.line_code,
    ls.line_nickname,
    ls.genetic_background,
    ls.line_transgene_rollup
  FROM public.v11_fish_line_star ls
),
line_instances AS (
  SELECT
    fi.line_id,
    COUNT(*) AS n_instances
  FROM public.fish_instances_v10 fi
  GROUP BY fi.line_id
),
marker_line AS (
  SELECT
    fi.line_id,
    COUNT(DISTINCT mr.fish_instance_id) AS n_marker_fish,
    MAX(mr.n_constructs)                AS line_n_constructs,
    MAX(mr.n_fluors)                    AS line_n_fluors,
    COALESCE(
      string_agg(
        DISTINCT NULLIF(mr.fluor_tag_rollup, ''),
        '||'
      ),
      ''
    ) AS line_fluor_tag_rollup,
    COALESCE(
      string_agg(
        DISTINCT NULLIF(mr.organelle_fluor_rollup, ''),
        '||'
      ),
      ''
    ) AS line_organelle_fluor_rollup
  FROM public.v11_fish_marker_rollups mr
  JOIN public.fish_instances_v10 fi
    ON fi.id = mr.fish_instance_id
  GROUP BY fi.line_id
)
SELECT
  lc.line_transgene_rollup AS group_transgene_rollup,
  string_agg(DISTINCT lc.line_code, '||' ORDER BY lc.line_code)           AS group_line_codes,
  string_agg(DISTINCT lc.line_nickname, '||' ORDER BY lc.line_nickname)   AS group_line_nicknames,
  string_agg(DISTINCT lc.genetic_background, '||' ORDER BY lc.genetic_background) AS group_genetic_backgrounds,
  COUNT(*)                                                                AS n_lines,
  COALESCE(SUM(li.n_instances), 0)                                       AS n_instances,
  COALESCE(
    string_agg(
      DISTINCT NULLIF(ml.line_fluor_tag_rollup, ''),
      '||'
    ),
    ''
  ) AS all_fluor_tag_rollup,
  COALESCE(
    string_agg(
      DISTINCT NULLIF(ml.line_organelle_fluor_rollup, ''),
      '||'
    ),
    ''
  ) AS all_organelle_fluor_rollup
FROM line_core lc
LEFT JOIN line_instances li
  ON li.line_id = lc.line_id
LEFT JOIN marker_line ml
  ON ml.line_id = lc.line_id
WHERE lc.line_transgene_rollup IS NOT NULL
  AND lc.line_transgene_rollup <> ''
GROUP BY lc.line_transgene_rollup
ORDER BY lc.line_transgene_rollup;

COMMENT ON VIEW public.v11_fish_group_star IS
  'v11 fish group star: groups of lines sharing the same transgene_base_code set (ignoring allele_number), with line counts, instance counts, and marker rollups.';

COMMIT;
