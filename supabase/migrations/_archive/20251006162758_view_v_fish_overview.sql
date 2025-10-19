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
    -- genotype summary
    DATE_PART('day', NOW() - f.date_birth)::int AS age_days,
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
    ) AS genotype_text
FROM public.fish AS f
ORDER BY f.created_at DESC;

COMMIT;
