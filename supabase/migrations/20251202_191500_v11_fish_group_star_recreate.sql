BEGIN;

DROP VIEW IF EXISTS public.v11_fish_group_star CASCADE;

CREATE VIEW public.v11_fish_group_star AS
WITH base AS (
  SELECT
    fl.fish_group_id,
    array_agg(DISTINCT fl.line_code ORDER BY fl.line_code)          AS line_codes,
    array_agg(DISTINCT fl.nickname ORDER BY fl.nickname)            AS line_nicknames,
    array_agg(DISTINCT fl.genetic_background ORDER BY fl.genetic_background) AS bgs,
    COUNT(DISTINCT fl.id)                                           AS n_lines,
    COUNT(*)                                                        AS n_instances
  FROM public.fish_instances_v10 fi
  JOIN public.fish_lines fl
    ON fl.id = fi.line_id
  LEFT JOIN public.fish_groups fg
    ON fg.id = fl.fish_group_id
  GROUP BY fl.fish_group_id
),
alleles AS (
  SELECT
    fl.fish_group_id,
    string_agg(
      (c.construct_code || ':' || j.allele_number::text),
      ' + ' ORDER BY c.construct_code, j.allele_number
    ) AS group_transgene_rollup
  FROM public.fish_lines fl
  JOIN public.fish_groups fg
    ON fg.id = fl.fish_group_id
  JOIN public.join_fish_group_alleles j
    ON j.fish_group_id = fg.id
  JOIN public.constructs c
    ON c.id = j.construct_id
  GROUP BY fl.fish_group_id
)
SELECT
  COALESCE(a.group_transgene_rollup, '')                                  AS group_transgene_rollup,
  COALESCE(array_to_string(b.line_codes, '||'), '')                       AS group_line_codes,
  COALESCE(array_to_string(b.line_nicknames, '||'), '')                   AS group_line_nicknames,
  COALESCE(array_to_string(b.bgs, '||'), '')                              AS group_genetic_backgrounds,
  b.n_lines,
  b.n_instances,
  ''::text                                                                AS all_fluor_tag_rollup,
  ''::text                                                                AS all_organelle_fluor_rollup
FROM base b
LEFT JOIN alleles a
  ON a.fish_group_id = b.fish_group_id;

COMMENT ON VIEW public.v11_fish_group_star IS
'Group-level fish rollups (one row per fish_group_id): transgene/allele rollup and line/background counts. Marker rollups are recomputed in the UI.';

COMMIT;
