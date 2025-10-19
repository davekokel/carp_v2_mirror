CREATE OR REPLACE VIEW public.vw_fish_overview_with_label AS
SELECT
    v.*,

    -- batch & created_by enrichments (unchanged)
    sx.slul_base AS transgene_base_code_from_sidecar,
    sx.slul_num AS allele_number_from_sidecar,

    -- Sidecar match (code OR name → same fish)
    sx.slul_code AS allele_code_from_sidecar,
    COALESCE(
        NULLIF(TRIM(v.transgene_base_code), ''),
        sx.slul_base,
        (
            SELECT fta2.transgene_base_code FROM public.fish_transgene_alleles AS fta2
            WHERE fta2.fish_id = f.id_uuid
            ORDER BY fta2.allele_number NULLS LAST LIMIT 1
        )
    )::text AS transgene_base_code_filled,
    COALESCE(
        NULLIF(TRIM(sx.slul_code), ''),
        (
            SELECT ta.allele_code FROM public.fish_transgene_alleles AS fta2
            INNER JOIN public.transgene_alleles AS ta
                ON
                    fta2.transgene_base_code = ta.transgene_base_code
                    AND fta2.allele_number = ta.allele_number
            WHERE fta2.fish_id = f.id_uuid
            ORDER BY fta2.allele_number NULLS LAST LIMIT 1
        ),
        NULLIF(TRIM(v.allele_number::text), ''),
        NULLIF(TRIM(v.transgene_name), '')
    )::text AS allele_code_filled,

    -- Filled base
    COALESCE(
        NULLIF(TRIM(v.allele_number::text), ''),
        sx.slul_num::text,
        (
            SELECT fta2.allele_number::text FROM public.fish_transgene_alleles AS fta2
            WHERE fta2.fish_id = f.id_uuid
            ORDER BY fta2.allele_number NULLS LAST LIMIT 1
        )
    )::text AS allele_number_filled,

    -- Filled allele_code (prefer sidecar → link-table → v.legacy/number)
    COALESCE(
        NULLIF(TRIM(v.transgene_name), ''),
        (
            SELECT tg.transgene_name FROM public.transgenes AS tg
            WHERE tg.transgene_base_code = sx.slul_base LIMIT 1
        ),
        NULLIF(TRIM(v.transgene_base_code), '')
    )::text AS transgene_name_filled,

    -- Filled allele_number (kept for reference)
    CASE
        WHEN
            COALESCE(NULLIF(TRIM(v.transgene_base_code), ''), sx.slul_base) IS NOT NULL
            AND COALESCE(
                NULLIF(TRIM(sx.slul_code), ''),
                NULLIF(TRIM(v.allele_number::text), ''),
                NULLIF(TRIM(v.transgene_name), '')
            ) IS NOT NULL
            THEN
                'Tg('
                || LOWER(
                    COALESCE(NULLIF(TRIM(v.transgene_base_code), ''), sx.slul_base)
                )
                || ')'
                || COALESCE(NULLIF(TRIM(sx.slul_code), ''), NULLIF(TRIM(v.allele_number::text), ''), NULLIF(TRIM(v.transgene_name), ''))
    END::text AS transgene_pretty_filled,

    -- Human name (kept, fallback chain)
    COALESCE(sb.batch_label, fsb.seed_batch_id) AS batch_label,

    -- Pretty: Tg(<lower(base with padded digits)>)<allele_code>
    COALESCE(NULLIF(TRIM(v.created_by), ''), NULLIF(TRIM(f.created_by), '')) AS created_by_enriched

FROM public.vw_fish_overview AS v
LEFT JOIN public.fish AS f
    ON UPPER(TRIM(f.fish_code)) = UPPER(TRIM(v.fish_code))

LEFT JOIN public.fish_seed_batches AS fsb
    ON f.id_uuid = fsb.fish_id
LEFT JOIN public.seed_batches AS sb
    ON fsb.seed_batch_id = sb.seed_batch_id

-- Sidecar (match same fish via code OR name)
LEFT JOIN LATERAL (
    SELECT
        slul.transgene_base_code AS slul_base,
        slul.allele_number AS slul_num,
        slul.allele_code AS slul_code
    FROM public.seed_last_upload_links AS slul
    INNER JOIN public.fish AS f2
        ON
            UPPER(TRIM(f2.fish_code)) = UPPER(TRIM(slul.fish_code))
            OR UPPER(TRIM(f2.name)) = UPPER(TRIM(slul.fish_code))
    WHERE f2.id_uuid = f.id_uuid
    LIMIT 1
) AS sx ON TRUE;
