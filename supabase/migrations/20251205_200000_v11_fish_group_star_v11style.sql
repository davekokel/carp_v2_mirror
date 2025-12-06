BEGIN;

DROP VIEW IF EXISTS public.v11_fish_group_star;

CREATE VIEW public.v11_fish_group_star AS
WITH line_allele_base AS (
  SELECT
    fl.id            AS line_id,
    fl.line_code,
    fl.nickname,
    fl.genetic_background,
    c.construct_code AS base_code
  FROM public.fish_lines fl
  JOIN public.join_line_alleles jla
    ON jla.line_id = fl.id
  JOIN public.constructs c
    ON c.id = jla.construct_id
),
line_group_key AS (
  -- group key: canonical combination of construct_code values per line
  SELECT
    lab.line_id,
    lab.line_code,
    lab.nickname,
    lab.genetic_background,
    string_agg(
      DISTINCT lab.base_code,
      ' + ' ORDER BY lab.base_code
    ) AS group_transgene_rollup
  FROM line_allele_base lab
  GROUP BY
    lab.line_id,
    lab.line_code,
    lab.nickname,
    lab.genetic_background
),
line_marker_rollups AS (
  -- marker rollups per line from v11_fish_marker_rollups
  SELECT
    fi.line_id,
    COUNT(DISTINCT mr.fish_instance_id)         AS n_marker_fish,
    MAX(mr.n_constructs)                        AS line_n_constructs,
    MAX(mr.n_fluors)                            AS line_n_fluors,
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
),
line_instance_counts AS (
  SELECT
    fi.line_id,
    COUNT(*)::int AS n_instances
  FROM public.fish_instances_v10 fi
  GROUP BY fi.line_id
),
line_enriched AS (
  SELECT
    lgk.line_id,
    lgk.line_code,
    lgk.nickname,
    lgk.genetic_background,
    lgk.group_transgene_rollup,
    COALESCE(li.n_instances, 0)           AS n_instances,
    COALESCE(lmr.line_n_constructs, 0)    AS n_constructs,
    COALESCE(lmr.line_n_fluors, 0)        AS n_fluors,
    COALESCE(lmr.line_fluor_tag_rollup, '')       AS all_fluor_tag_rollup,
    COALESCE(lmr.line_organelle_fluor_rollup, '') AS all_organelle_fluor_rollup
  FROM line_group_key lgk
  LEFT JOIN line_instance_counts li
    ON li.line_id = lgk.line_id
  LEFT JOIN line_marker_rollups lmr
    ON lmr.line_id = lgk.line_id
)
SELECT
  le.group_transgene_rollup,
  string_agg(DISTINCT le.line_code, '||' ORDER BY le.line_code) AS group_line_codes,
  string_agg(DISTINCT le.nickname, '||' ORDER BY le.nickname)   AS group_line_nicknames,
  string_agg(DISTINCT le.genetic_background, '||' ORDER BY le.genetic_background) AS group_genetic_backgrounds,
  COUNT(DISTINCT le.line_id)::int  AS n_lines,
  COALESCE(SUM(le.n_instances), 0) AS n_instances,
  COALESCE(
    string_agg(
      DISTINCT NULLIF(le.all_fluor_tag_rollup, ''),
      '||'
    ),
    ''
  ) AS all_fluor_tag_rollup,
  COALESCE(
    string_agg(
      DISTINCT NULLIF(le.all_organelle_fluor_rollup, ''),
      '||'
    ),
    ''
  ) AS all_organelle_fluor_rollup
FROM line_enriched le
GROUP BY le.group_transgene_rollup
ORDER BY le.group_transgene_rollup;

COMMENT ON VIEW public.v11_fish_group_star IS
'v11 fish "group" star view: groups defined by canonical combinations of construct_code (transgene_base_code) across lines.';

COMMIT;
