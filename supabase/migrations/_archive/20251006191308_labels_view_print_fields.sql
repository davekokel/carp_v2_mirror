BEGIN;

DROP VIEW IF EXISTS public.v_fish_overview_with_label;

CREATE VIEW public.v_fish_overview_with_label AS
WITH base AS (
    SELECT
        f.fish_code,
        f.name,
        f.nickname,
        f.line_building_stage,
        f.date_birth,
        f.genetic_background,
        f.created_at
    FROM public.fish AS f
),

allele AS (
    -- pick one allele per fish (alphabetical base_code, then smallest allele_number)
    SELECT DISTINCT ON (f2.fish_code)
        f2.fish_code,
        l.transgene_base_code,
        l.allele_number,
        ta.allele_nickname
    FROM public.fish_transgene_alleles AS l
    INNER JOIN public.fish AS f2 ON l.fish_id = f2.id_uuid
    LEFT JOIN public.transgene_alleles AS ta
        ON
            l.transgene_base_code = ta.transgene_base_code
            AND l.allele_number = ta.allele_number
    ORDER BY f2.fish_code, l.transgene_base_code, l.allele_number NULLS LAST
),

batch AS (
    -- most recent seed_batch_id per fish
    SELECT DISTINCT ON (f3.fish_code)
        f3.fish_code,
        m.seed_batch_id
    FROM public.fish_seed_batches_map AS m
    INNER JOIN public.fish AS f3 ON m.fish_id = f3.id_uuid
    ORDER BY f3.fish_code ASC, m.logged_at DESC NULLS LAST, m.created_at DESC NULLS LAST
)

SELECT
    b.*,
    -- “filled” fields for downstream use
    a.transgene_base_code AS transgene_base_code_filled,
    a.allele_number::text AS allele_code_filled,
    a.allele_nickname AS allele_name_filled,
    batch.seed_batch_id,
    batch.seed_batch_id AS batch_label,
    -- print-ready (coalesced) fields
    ((CURRENT_DATE - b.date_birth) / 7)::int AS age_weeks,
    COALESCE(b.nickname, '') AS nickname_print,
    COALESCE(b.genetic_background, '') AS genetic_background_print,
    COALESCE(b.line_building_stage, '') AS line_building_stage_print,
    COALESCE(TO_CHAR(b.date_birth, 'YYYY-MM-DD'), '') AS date_birth_print,
    -- convenience
    CASE
        WHEN a.transgene_base_code IS NULL THEN ''
        WHEN a.allele_number IS NOT NULL THEN a.transgene_base_code || '-' || a.allele_number::text
        WHEN a.allele_nickname IS NOT NULL THEN a.transgene_base_code || ' ' || a.allele_nickname
        ELSE a.transgene_base_code
    END AS genotype_print
FROM base AS b
LEFT JOIN allele AS a ON b.fish_code = a.fish_code
LEFT JOIN batch USING (fish_code)
ORDER BY b.fish_code;

COMMIT;
