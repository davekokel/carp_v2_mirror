-- Redeclare v_fish_standard_clean with explicit column list and corrected body.
-- Column order and names are set here; body derives allele_name and genotype properly.

CREATE OR REPLACE VIEW public.v_fish_standard_clean
  (fish_code,
   name,
   nickname,
   genetic_background,
   line_building_stage,
   birth_date,
   created_time,
   created_by,
   transgene_base_code,
   allele_number,
   allele_nickname,
   allele_name,
   transgene_pretty_nickname,
   transgene_pretty_name,
   genotype)
AS
SELECT
  f.fish_code,
  f.name,
  f.nickname,
  f.genetic_background,
  f.line_building_stage,
  f.date_birth                           AS birth_date,
  f.created_at                           AS created_time,
  f.created_by,
  fta.transgene_base_code,
  fta.allele_number,
  r.allele_nickname,
  ('gu' || fta.allele_number::text)      AS allele_name,
  ('Tg('||fta.transgene_base_code||')'||coalesce(r.allele_nickname,''))            AS transgene_pretty_nickname,
  ('Tg('||fta.transgene_base_code||')'||('gu'||fta.allele_number::text))           AS transgene_pretty_name,
  (
    SELECT string_agg(
             'Tg('||fta2.transgene_base_code||')'||('gu'||fta2.allele_number::text),
             '; ' ORDER BY fta2.transgene_base_code, fta2.allele_number
           )
    FROM public.fish_transgene_alleles fta2
    WHERE fta2.fish_id = f.id
  )                                          AS genotype
FROM public.fish f
LEFT JOIN public.fish_transgene_alleles fta
       ON fta.fish_id = f.id
LEFT JOIN public.transgene_allele_registry r
       ON r.transgene_base_code = fta.transgene_base_code
      AND r.allele_number       = fta.allele_number;
