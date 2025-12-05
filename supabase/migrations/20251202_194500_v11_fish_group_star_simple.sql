BEGIN;

DROP VIEW IF EXISTS public.v11_fish_group_star;

CREATE VIEW public.v11_fish_group_star AS
WITH base AS (
  SELECT
    fg.id::text AS fish_group_id,
    g.genotype_basecodes AS group_transgene_rollup,
    array_agg(DISTINCT fl.line_code ORDER BY fl.line_code)             AS group_line_codes_arr,
    array_agg(DISTINCT fl.nickname ORDER BY fl.nickname)               AS group_line_nicknames_arr,
    array_agg(DISTINCT fl.genetic_background ORDER BY fl.genetic_background) AS group_genetic_backgrounds_arr,
    count(DISTINCT fl.id)                                              AS n_lines,
    count(DISTINCT fi.id)                                              AS n_instances
  FROM public.fish_groups fg
  JOIN public.genotypes_v11 g
    ON g.genotype_code = fg.genotype_key
  JOIN public.fish_lines fl
    ON fl.fish_group_id = fg.id
  JOIN public.fish_instances_v10 fi
    ON fi.line_id = fl.id
  GROUP BY
    fg.id,
    g.genotype_basecodes
)
SELECT
  b.group_transgene_rollup,
  array_to_string(b.group_line_codes_arr, '||')             AS group_line_codes,
  array_to_string(b.group_line_nicknames_arr, '||')         AS group_line_nicknames,
  array_to_string(b.group_genetic_backgrounds_arr, '||')    AS group_genetic_backgrounds,
  b.n_lines,
  b.n_instances,
  ''::text                                                  AS all_fluor_tag_rollup,
  ''::text                                                  AS all_organelle_fluor_rollup
FROM base b;

COMMENT ON VIEW public.v11_fish_group_star IS
'Group-level fish rollups (one row per fish_group_id). Marker rollups are recomputed in the UI from line-level rollups.';

COMMIT;
