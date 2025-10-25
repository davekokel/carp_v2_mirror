-- Add a computed pretty label: Tg(<lower(base)>)<allele>
CREATE OR REPLACE VIEW public.v_fish_overview_with_label AS
SELECT
    v.*,

    -- batch label via mapping
    COALESCE(
        NULLIF(TRIM(v.transgene_base_code), ''),
        sx.slul_base,
        (
            SELECT fta2.transgene_base_code
            FROM public.fish_transgene_alleles AS fta2
            WHERE fta2.fish_id = f.id_uuid
            ORDER BY fta2.allele_number NULLS LAST
            LIMIT 1
        )
    )::text AS transgene_base_code_filled,

    -- created_by enrichment
    COALESCE(
        NULLIF(TRIM(v.allele_number::text), ''),
        sx.slul_num::text,
        (
            SELECT fta2.allele_number::text
            FROM public.fish_transgene_alleles AS fta2
            WHERE fta2.fish_id = f.id_uuid
            ORDER BY fta2.allele_number NULLS LAST
            LIMIT 1
        )
    )::text AS allele_number_filled,

    /* Filled base code (TEXT) – prefer sidecar -> link-table -> v.* */
    COALESCE(
        NULLIF(TRIM(v.transgene_name), ''),
        (
            SELECT COALESCE(tg.transgene_name, sx.slul_base)
            FROM (SELECT 1) AS _
            LEFT JOIN public.transgenes AS tg
                ON tg.transgene_base_code = sx.slul_base
        ),
        (
            SELECT COALESCE(tg.transgene_name, fta2.transgene_base_code)
            FROM public.fish_transgene_alleles AS fta2
            LEFT JOIN public.transgenes AS tg
                ON fta2.transgene_base_code = tg.transgene_base_code
            WHERE fta2.fish_id = f.id_uuid
            ORDER BY fta2.allele_number NULLS LAST
            LIMIT 1
        ),
        NULLIF(TRIM(v.transgene_base_code), '')
    )::text AS transgene_name_filled,

    /* Filled allele number (TEXT) – prefer sidecar -> link-table -> v.* */
    CASE
        WHEN
            COALESCE(
                NULLIF(TRIM(v.transgene_base_code), ''),
                sx.slul_base,
                (
                    SELECT fta2.transgene_base_code
                    FROM public.fish_transgene_alleles AS fta2
                    WHERE fta2.fish_id = f.id_uuid
                    ORDER BY fta2.allele_number NULLS LAST
                    LIMIT 1
                )
            ) IS NOT NULL
            AND
            COALESCE(
                NULLIF(TRIM(v.allele_number::text), ''),
                sx.slul_num::text,
                (
                    SELECT fta2.allele_number::text
                    FROM public.fish_transgene_alleles AS fta2
                    WHERE fta2.fish_id = f.id_uuid
                    ORDER BY fta2.allele_number NULLS LAST
                    LIMIT 1
                )
            ) IS NOT NULL
            THEN
                'Tg('
                || LOWER(
                    COALESCE(
                        NULLIF(TRIM(v.transgene_base_code), ''),
                        sx.slul_base,
                        (
                            SELECT fta2.transgene_base_code
                            FROM public.fish_transgene_alleles AS fta2
                            WHERE fta2.fish_id = f.id_uuid
                            ORDER BY fta2.allele_number NULLS LAST
                            LIMIT 1
                        )
                    )
                )
                || ')'
                || COALESCE(
                    NULLIF(TRIM(v.allele_number::text), ''),
                    sx.slul_num::text,
                    (
                        SELECT fta2.allele_number::text
                        FROM public.fish_transgene_alleles AS fta2
                        WHERE fta2.fish_id = f.id_uuid
                        ORDER BY fta2.allele_number NULLS LAST
                        LIMIT 1
                    )
                )
        ELSE
            COALESCE(
                NULLIF(TRIM(v.transgene_name), ''),
                (
                    SELECT COALESCE(tg.transgene_name, sx.slul_base)
                    FROM (SELECT 1) AS _
                    LEFT JOIN public.transgenes AS tg
                        ON tg.transgene_base_code = sx.slul_base
                ),
                (
                    SELECT COALESCE(tg.transgene_name, fta2.transgene_base_code)
                    FROM public.fish_transgene_alleles AS fta2
                    LEFT JOIN public.transgenes AS tg
                        ON fta2.transgene_base_code = tg.transgene_base_code
                    WHERE fta2.fish_id = f.id_uuid
                    ORDER BY fta2.allele_number NULLS LAST
                    LIMIT 1
                ),
                NULLIF(TRIM(v.transgene_base_code), '')
            )
    END::text AS transgene_pretty_filled,

    /* Filled human name (TEXT) – prefer v.*, else name-from-base, else link-table name, else base */
    COALESCE(sb.batch_label, fsb.seed_batch_id) AS batch_label,

    /* Pretty label: Tg(<lower(base)>)<allele> when both base and allele exist; else transgene_name_filled */
    COALESCE(NULLIF(TRIM(v.created_by), ''), NULLIF(TRIM(f.created_by), '')) AS created_by_enriched

FROM public.vw_fish_overview AS v

-- fish row for mapping and resolution
LEFT JOIN public.fish AS f
    ON UPPER(TRIM(f.fish_code)) = UPPER(TRIM(v.fish_code))

LEFT JOIN public.fish_seed_batches AS fsb
    ON f.id_uuid = fsb.fish_id
LEFT JOIN public.seed_batches AS sb
    ON fsb.seed_batch_id = sb.seed_batch_id

-- sidecar match: code OR name
LEFT JOIN LATERAL (
    SELECT
        slul.transgene_base_code AS slul_base,
        slul.allele_number AS slul_num
    FROM public.seed_last_upload_links AS slul
    INNER JOIN public.fish AS f2
        ON
            UPPER(TRIM(f2.fish_code)) = UPPER(TRIM(slul.fish_code))
            OR UPPER(TRIM(f2.name)) = UPPER(TRIM(slul.fish_code))
    WHERE f2.id_uuid = f.id_uuid
    LIMIT 1
) AS sx ON TRUE;
