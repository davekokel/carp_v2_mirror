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
geno AS (
  SELECT
    a.fish_code,
    string_agg(DISTINCT ('Tg('||a.transgene_base_code||')'||coalesce(a.allele_name,'')),
               '; ' ORDER BY a.transgene_base_code, coalesce(a.allele_name,''))             AS genotype,
    string_agg(DISTINCT a.transgene_base_code, '; ' ORDER BY a.transgene_base_code)        AS base_codes,
    string_agg(DISTINCT coalesce(a.allele_name,''), '; ' ORDER BY coalesce(a.allele_name,'')) AS allele_codes
  FROM alleles a
  GROUP BY a.fish_code
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
