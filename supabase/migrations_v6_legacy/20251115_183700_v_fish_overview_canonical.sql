BEGIN;

CREATE OR REPLACE VIEW public.v_fish_overview AS
WITH core AS (
  SELECT
    f.id,
    f.fish_code,
    f.nickname,
    f.birthday,
    f.genetic_background,
    f.in_breeding_stage,
    f.created_at
  FROM public.fish f
),
alleles AS (
  SELECT
    jfta.fish_id,
    jfta.transgene_base_code,
    ta.allele_number,
    ta.allele_name,
    ta.allele_nickname
  FROM public.join_fish_transgene_alleles jfta
  JOIN public.transgene_alleles ta
    ON ta.transgene_base_code = jfta.transgene_base_code
   AND ta.allele_number       = jfta.allele_number
),
geno AS (
  SELECT
    a.fish_id,
    string_agg(
      'Tg(' || a.transgene_base_code || ')' || a.allele_name,
      ' + ' ORDER BY a.transgene_base_code, a.allele_number
    ) AS transgene_canonical,
    string_agg(
      'Tg(' || a.transgene_base_code || ')' || a.allele_nickname,
      ' + ' ORDER BY a.transgene_base_code, a.allele_number
    ) AS transgene_nickname
  FROM alleles a
  GROUP BY a.fish_id
)
SELECT
  c.fish_code                                AS fish_code_display,
  c.fish_code                                AS fish_code_raw,
  c.nickname,
  c.birthday,
  c.genetic_background,
  c.in_breeding_stage                        AS line_building_stage,
  COALESCE(g.transgene_canonical, c.genetic_background) AS genotype_pretty,
  g.transgene_canonical                      AS markers,
  ''::text                                   AS fluors,
  ''::text                                   AS tags,
  ''::text                                   AS fusions,
  0::bigint                                  AS n_fusions,
  ''::text                                   AS dyes,
  c.created_at,
  g.transgene_canonical,
  g.transgene_nickname
FROM core c
LEFT JOIN geno g
  ON g.fish_id = c.id;

COMMIT;
