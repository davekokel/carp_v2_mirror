CREATE OR REPLACE VIEW public.v_fish_overview_with_label AS
WITH first_link AS (
    -- first allele per fish by allele_number asc (NULLS LAST)
    SELECT
        f.id_uuid AS fish_id,
        fta.transgene_base_code AS base,
        fta.allele_number AS num,
        ta.allele_code AS acode,
        ta.allele_name AS aname
    FROM public.fish AS f
    LEFT JOIN LATERAL (
        SELECT *
        FROM public.fish_transgene_alleles AS x
        WHERE x.fish_id = f.id_uuid
        ORDER BY x.allele_number NULLS LAST
        LIMIT 1
    ) AS fta ON TRUE
    LEFT JOIN public.transgene_alleles AS ta
        ON
            fta.transgene_base_code = ta.transgene_base_code
            AND fta.allele_number = ta.allele_number
)

SELECT
    v.*,

    COALESCE(NULLIF(TRIM(v.transgene_base_code), ''), fl.base)::text AS transgene_base_code_filled,
    COALESCE(NULLIF(TRIM(v.allele_number::text), ''), (fl.num)::text)::text AS allele_number_filled,

    COALESCE(fl.acode, fl.aname, NULLIF(TRIM(v.transgene_name), ''), fl.base)::text AS allele_code_filled,
    (
        CASE
            WHEN
                COALESCE(NULLIF(TRIM(v.transgene_base_code), ''), fl.base) IS NOT NULL
                AND COALESCE(NULLIF(TRIM(v.allele_number::text), ''), (fl.num)::text) IS NOT NULL
                THEN
                    'Tg('
                    || (
                        REGEXP_REPLACE(
                            LOWER(COALESCE(NULLIF(TRIM(v.transgene_base_code), ''), fl.base)), '[0-9]+$', ''
                        )
                        ||
                        LPAD(
                            REGEXP_REPLACE(
                                LOWER(COALESCE(NULLIF(TRIM(v.transgene_base_code), ''), fl.base)), '^[A-Za-z]+', ''
                            ),
                            4,
                            '0'
                        )
                    ) || ')'
                    || COALESCE(fl.acode, fl.aname, (fl.num)::text)
        END
    )::text AS transgene_pretty_filled,
    COALESCE(sb.batch_label, fsb.seed_batch_id) AS batch_label,

    COALESCE(NULLIF(TRIM(v.created_by), ''), NULLIF(TRIM(f.created_by), '')) AS created_by_enriched

FROM public.vw_fish_overview AS v
LEFT JOIN public.fish AS f
    ON UPPER(TRIM(f.fish_code)) = UPPER(TRIM(v.fish_code))
LEFT JOIN public.fish_seed_batches AS fsb ON f.id_uuid = fsb.fish_id
LEFT JOIN public.seed_batches AS sb ON fsb.seed_batch_id = sb.seed_batch_id
LEFT JOIN first_link AS fl ON f.id_uuid = fl.fish_id;
