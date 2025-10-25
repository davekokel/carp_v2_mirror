CREATE OR REPLACE VIEW public.v_fish_overview_with_label AS
SELECT
    v.*,

    -- batch label via mapping
    COALESCE(sb.batch_label, fsb.seed_batch_id) AS batch_label,

    -- created_by enrichment
    COALESCE(NULLIF(TRIM(v.created_by), ''), NULLIF(TRIM(f.created_by), '')) AS created_by_enriched,

    -- base code (text everywhere; prefer v.*, then sidecar, then link table)
    COALESCE(
        NULLIF(TRIM(v.transgene_base_code), ''),
        NULLIF(TRIM(slul.transgene_base_code), ''),
        (
            SELECT fta2.transgene_base_code
            FROM public.fish_transgene_alleles AS fta2
            WHERE fta2.fish_id = f.id_uuid
            ORDER BY fta2.allele_number NULLS LAST
            LIMIT 1
        )
    ) AS transgene_base_code_filled,

    -- allele number (ensure all args are integer)
    COALESCE(
        v.allele_number,
        NULLIF(TRIM((slul.allele_number)::text), '')::int,
        (
            SELECT fta2.allele_number
            FROM public.fish_transgene_alleles AS fta2
            WHERE fta2.fish_id = f.id_uuid
            ORDER BY fta2.allele_number NULLS LAST
            LIMIT 1
        )
    ) AS allele_number_filled,

    -- transgene name (text; prefer v.*, else sidecar base→name, else link-table base→name)
    COALESCE(
        NULLIF(TRIM(v.transgene_name), ''),
        (
            SELECT COALESCE(tg.transgene_name, slul.transgene_base_code)
            FROM (SELECT 1) AS _
            LEFT JOIN public.transgenes AS tg
                ON tg.transgene_base_code = slul.transgene_base_code
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
    ) AS transgene_name_filled

FROM public.vw_fish_overview AS v
LEFT JOIN public.fish AS f
    ON UPPER(TRIM(f.fish_code)) = UPPER(TRIM(v.fish_code))
LEFT JOIN public.fish_seed_batches AS fsb
    ON f.id_uuid = fsb.fish_id
LEFT JOIN public.seed_batches AS sb
    ON fsb.seed_batch_id = sb.seed_batch_id
LEFT JOIN public.seed_last_upload_links AS slul
    ON UPPER(TRIM(slul.fish_code)) = UPPER(TRIM(v.fish_code));
