BEGIN;

CREATE OR REPLACE VIEW public.v_fish
( id, fish_code, name, nickname, genotype, genetic_background, stage,
  date_birth, age_days, created_at, created_by,
  batch_display, transgene_base_code, allele_code, treatments_rollup, n_living_tanks ) AS
WITH alleles AS (
  SELECT
    f.fish_code,
    fta.transgene_base_code,
    ta.allele_name
  FROM public.fish f
  LEFT JOIN public.fish_transgene_alleles fta ON fta.fish_id = f.id
  LEFT JOIN public.transgene_alleles ta
         ON ta.transgene_base_code = fta.transgene_base_code
        AND ta.allele_number       = fta.allele_number
),
-- Build the exact text fragments once so we can use the *same* expression for DISTINCT and ORDER BY
geno_prep AS (
  SELECT
    a.fish_code,
    ('Tg('||a.transgene_base_code||')'||coalesce(a.allele_name,''))::text AS geno_piece,
    a.transgene_base_code::text                                          AS base_piece,
    coalesce(a.allele_name,'')::text                                     AS allele_piece
  FROM alleles a
),
geno AS (
  SELECT
    gp.fish_code,
    string_agg(DISTINCT gp.geno_piece,  '; ' ORDER BY gp.geno_piece)  AS genotype,
    string_agg(DISTINCT gp.base_piece,  '; ' ORDER BY gp.base_piece)  AS base_codes,
    string_agg(DISTINCT gp.allele_piece,'; ' ORDER BY gp.allele_piece) AS allele_codes
  FROM geno_prep gp
  GROUP BY gp.fish_code
),
living AS (
  SELECT vt.fish_code, count(*)::int AS n_living_tanks
  FROM public.v_tanks vt
  WHERE coalesce(vt.fish_code,'') <> '' AND vt.status IN ('new','active')
  GROUP BY vt.fish_code
)
SELECT
  f.id,
  f.fish_code,
  coalesce(f.name,'')                                  AS name,
  coalesce(f.nickname,'')                              AS nickname,
  coalesce(g.genotype,'')                              AS genotype,
  coalesce(f.genetic_background,'')                    AS genetic_background,
  coalesce(f.line_building_stage,'')                   AS stage,
  f.date_birth,
  (current_date - f.date_birth)::int                   AS age_days,
  f.created_at,
  f.created_by,
  ''::text                                             AS batch_display,
  coalesce(g.base_codes,'')                            AS transgene_base_code,
  coalesce(g.allele_codes,'')                          AS allele_code,
  ''::text                                             AS treatments_rollup,
  coalesce(l.n_living_tanks,0)                         AS n_living_tanks
FROM public.fish f
LEFT JOIN geno   g USING (fish_code)
LEFT JOIN living l USING (fish_code)
ORDER BY f.created_at DESC NULLS LAST, f.fish_code;

COMMIT;
