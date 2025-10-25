BEGIN;
DROP VIEW IF EXISTS public.v_fish_overview_with_label;
CREATE VIEW public.v_fish_overview_with_label AS
SELECT
    v.*,
    fa.transgene_base_code_filled,
    fa.allele_code_filled,
    fa.allele_name_filled
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
) AS fa ON TRUE;
COMMIT;
