BEGIN;

DROP VIEW IF EXISTS public.v_fish_overview CASCADE;
CREATE VIEW public.v_fish_overview AS
SELECT
  f.fish_code,
  f.name,
  f.nickname,
  f.line_building_stage,
  f.date_birth,
  f.genetic_background,
  f.created_at,
  NULLIF(
    array_to_string(
      ARRAY(
        SELECT (fa2.transgene_base_code || '^' || fa2.allele_number::text)
        FROM public.fish_transgene_alleles fa2
        WHERE fa2.fish_id = f.id_uuid
        ORDER BY fa2.transgene_base_code, fa2.allele_number
      ),
      '; '
    ),
    ''
  ) AS genotype_text,
  DATE_PART('day', now() - f.date_birth)::int AS age_days
FROM public.fish f
ORDER BY f.created_at DESC;

DROP VIEW IF EXISTS public.vw_fish_overview_with_label;
CREATE VIEW public.vw_fish_overview_with_label AS
SELECT * FROM public.v_fish_overview;


COMMIT;
