BEGIN;

CREATE OR REPLACE VIEW public.v11_fish_group_star AS
WITH L AS (
  SELECT
    line_id,
    line_code,
    line_nickname,
    genetic_background,
    line_transgene_rollup
  FROM public.v11_fish_line_star
)
SELECT
  line_transgene_rollup AS group_transgene_rollup,
  string_agg(DISTINCT line_code, '||' ORDER BY line_code) AS group_line_codes,
  string_agg(DISTINCT line_nickname, '||' ORDER BY line_nickname) AS group_line_nicknames,
  string_agg(DISTINCT genetic_background, '||' ORDER BY genetic_background) AS group_genetic_backgrounds
FROM L
WHERE line_transgene_rollup IS NOT NULL
  AND line_transgene_rollup <> ''
GROUP BY line_transgene_rollup;

COMMENT ON VIEW public.v11_fish_group_star IS
  'v11 fish group star: groups of lines sharing the same transgene_base_code set (ignoring allele_number), derived from v11_fish_line_star.';

COMMIT;
