CREATE OR REPLACE VIEW public.v_fish_overview_with_label AS
SELECT
    v.*,

    -- batch label via mapping (unchanged)
    COALESCE(
        NULLIF(TRIM(v.transgene_base_code), ''),
        NULLIF(TRIM(sx.slul_base), ''),
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
        NULLIF(TRIM(sx.slul_num::text), ''),
        (
            SELECT fta2.allele_number::text
            FROM public.fish_transgene_alleles AS fta2
            WHERE fta2.fish_id = f.id_uuid
            ORDER BY fta2.allele_number NULLS LAST
            LIMIT 1
        )
    )::text AS allele_number_filled,

    /* Prefer sidecar (matched by code OR name) → then link-table → then v.* */
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
        )
    )::text AS transgene_name_filled,

    COALESCE(sb.batch_label, fsb.seed_batch_id) AS batch_label,

    COALESCE(NULLIF(TRIM(v.created_by), ''), NULLIF(TRIM(f.created_by), '')) AS created_by_enriched

FROM public.vw_fish_overview AS v

-- Resolve the fish row once (by code) for batch/created_by and for sidecar matching
LEFT JOIN public.fish AS f
    ON UPPER(TRIM(f.fish_code)) = UPPER(TRIM(v.fish_code))

LEFT JOIN public.fish_seed_batches AS fsb
    ON f.id_uuid = fsb.fish_id
LEFT JOIN public.seed_batches AS sb
    ON fsb.seed_batch_id = sb.seed_batch_id

-- Sidecar: match to the same fish by code OR name
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
