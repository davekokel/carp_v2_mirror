BEGIN;

DROP VIEW IF EXISTS public.v11_fish_group_star;
DROP VIEW IF EXISTS public.v11_fish_line_star;

CREATE VIEW public.v11_fish_line_star AS
WITH base AS (
  SELECT
    fl.id::uuid              AS line_id,
    fl.line_code             AS line_code,
    fl.nickname              AS line_nickname,
    fl.genetic_background    AS genetic_background,
    fl.line_building_stage   AS line_building_stage,
    fl.construct_code        AS line_construct_code,
    fi.id::uuid              AS fish_instance_id,
    fi.birthday              AS birthday,
    fis.genotype_pretty      AS genotype_pretty
  FROM public.fish_lines fl
  LEFT JOIN public.fish_instances_v10 fi
    ON fi.line_id = fl.id
  LEFT JOIN public.v11_fish_instance_star fis
    ON fis.fish_instance_id = fi.id
)
SELECT
  base.line_id,
  base.line_code,
  MAX(base.line_nickname)            AS line_nickname,
  MAX(base.genetic_background)       AS genetic_background,
  MAX(base.line_building_stage)      AS line_building_stage,
  MAX(base.line_construct_code)      AS line_construct_code,
  MAX(base.line_construct_code)      AS line_transgene_rollup,
  MIN(base.birthday)                 AS first_birthday,
  MAX(base.birthday)                 AS last_birthday,
  COUNT(base.fish_instance_id)       AS n_instances,
  MAX(base.genotype_pretty)          AS genotype_pretty
FROM base
GROUP BY
  base.line_id,
  base.line_code
ORDER BY
  base.line_code;

COMMENT ON VIEW public.v11_fish_line_star IS
  'v11 line star: per fish_line aggregates over fish_instances and v11_fish_instance_star; line_transgene_rollup currently uses line_construct_code as a fallback.';

CREATE VIEW public.v11_fish_group_star AS
WITH line_star AS (
  SELECT
    v11_fish_line_star.line_id,
    v11_fish_line_star.line_code,
    v11_fish_line_star.line_nickname,
    v11_fish_line_star.genetic_background,
    v11_fish_line_star.line_building_stage,
    v11_fish_line_star.line_transgene_rollup
  FROM public.v11_fish_line_star
), grouped AS (
  SELECT
    line_star.line_transgene_rollup,
    string_agg(DISTINCT line_star.line_code, '||' ORDER BY line_star.line_code)           AS group_line_codes,
    string_agg(DISTINCT line_star.line_nickname, '||' ORDER BY line_star.line_nickname)   AS group_line_nicknames,
    string_agg(DISTINCT line_star.genetic_background, '||' ORDER BY line_star.genetic_background) AS group_genetic_backgrounds
  FROM line_star
  WHERE line_star.line_transgene_rollup IS NOT NULL
    AND line_star.line_transgene_rollup <> ''
  GROUP BY line_star.line_transgene_rollup
)
SELECT
  line_transgene_rollup AS group_transgene_rollup,
  group_line_codes,
  group_line_nicknames,
  group_genetic_backgrounds
FROM grouped;

COMMENT ON VIEW public.v11_fish_group_star IS
  'v11 fish group star: groups of lines sharing the same line_transgene_rollup (currently based on line_construct_code).';

COMMIT;
