BEGIN;

DROP VIEW IF EXISTS public.v_fish_label_fields CASCADE;

CREATE VIEW public.v_fish_label_fields AS
SELECT
    f.fish_code,
    f.nickname,                                 -- include nickname
    f.name,
    NULL::text AS base_code,       -- not used by labels
    NULL::text AS tg_nick,         -- legacy; we print genetic_background instead
    f.line_building_stage AS stage,
    f.date_birth AS dob,
    /* genotype like base^number ; base^number (stable order) */
    f.genetic_background,
    NULLIF(
        ARRAY_TO_STRING(
            ARRAY(
                SELECT (fa2.transgene_base_code || '^' || fa2.allele_number::text)
                FROM public.fish_transgene_alleles AS fa2
                WHERE fa2.fish_id = f.id_uuid
                ORDER BY fa2.transgene_base_code, fa2.allele_number
            ),
            '; '
        ),
        ''
    ) AS genotype
FROM public.fish AS f;

COMMIT;
