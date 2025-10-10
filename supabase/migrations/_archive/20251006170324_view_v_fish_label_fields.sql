BEGIN;

DROP VIEW IF EXISTS public.v_fish_label_fields CASCADE;
CREATE VIEW public.v_fish_label_fields AS
SELECT
  f.fish_code,
  f.nickname,
  f.name,
  NULL::text              AS base_code,
  NULL::text              AS tg_nick,
  f.line_building_stage   AS stage,
  f.date_birth            AS dob,
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
  ) AS genotype,
  f.genetic_background
FROM public.fish f;


COMMIT;
