BEGIN;
DROP VIEW IF EXISTS public.vw_fish_overview_with_label;
CREATE VIEW public.vw_fish_overview_with_label AS
SELECT
    v.*,
    fa.transgene_base_code_filled,
    fa.allele_code_filled,
    fa.allele_name_filled,
    mb.seed_batch_id,
    mb.seed_batch_id AS batch_label,
    CASE
        WHEN v.date_birth IS NOT NULL
            THEN ((CURRENT_DATE - v.date_birth) / 7)::int
        ELSE NULL::int
    END AS age_weeks
FROM public.v_fish_overview AS v
LEFT JOIN LATERAL (
    SELECT
        l.transgene_base_code AS transgene_base_code_filled,
        l.allele_number::text AS allele_code_filled,
        ta.allele_nickname AS allele_name_filled
    FROM public.fish_transgene_alleles AS l
    INNER JOIN public.fish AS f2 ON l.fish_id = f2.id_uuid
    LEFT JOIN public.transgene_alleles AS ta
        ON
            l.transgene_base_code = ta.transgene_base_code
            AND l.allele_number = ta.allele_number
    WHERE f2.fish_code = v.fish_code
    ORDER BY l.transgene_base_code, l.allele_number
    LIMIT 1
) AS fa ON TRUE
LEFT JOIN LATERAL (
    SELECT m.seed_batch_id
    FROM public.fish_seed_batches_map AS m
    INNER JOIN public.fish AS f3 ON m.fish_id = f3.id_uuid
    WHERE f3.fish_code = v.fish_code
    ORDER BY m.logged_at DESC NULLS LAST, m.created_at DESC NULLS LAST
    LIMIT 1
) AS mb ON TRUE;
COMMIT;
