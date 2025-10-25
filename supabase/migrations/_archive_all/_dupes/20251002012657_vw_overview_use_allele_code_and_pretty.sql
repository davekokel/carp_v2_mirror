-- 1) Sidecar: ensure allele_code exists
ALTER TABLE public.seed_last_upload_links
ADD COLUMN IF NOT EXISTS allele_code text;

-- 2) Rebuild the labeled overview view without renaming existing columns.
--    We append allele_code_filled (new) and recompute transgene_pretty_filled (existing name).
CREATE OR REPLACE VIEW public.v_fish_overview_with_label AS
WITH
-- Pick the first linked allele (by allele_number asc, NULLS LAST) for this fish_id
linkx AS (
    SELECT
        f.id_uuid AS fish_id,
        fta.transgene_base_code AS l_base,
        fta.allele_number AS l_num,
        ta.allele_code AS l_code,
        ta.allele_name AS l_name
    FROM public.fish AS f
    LEFT JOIN LATERAL (
        SELECT *
        FROM public.fish_transgene_alleles AS fta2
        WHERE fta2.fish_id = f.id_uuid
        ORDER BY fta2.allele_number NULLS LAST
        LIMIT 1
    ) AS fta ON TRUE
    LEFT JOIN public.transgene_alleles AS ta
        ON
            fta.transgene_base_code = ta.transgene_base_code
            AND fta.allele_number = ta.allele_number
),

-- Sidecar row for the same fish, matching by code OR name
sidecar AS (
    SELECT
        f.id_uuid AS fish_id,
        slul.transgene_base_code AS s_base,
        slul.allele_number AS s_num,
        slul.allele_code AS s_code
    FROM public.fish AS f
    LEFT JOIN public.seed_last_upload_links AS slul
        ON
            UPPER(TRIM(slul.fish_code)) = UPPER(TRIM(f.fish_code))
            OR UPPER(TRIM(slul.fish_code)) = UPPER(TRIM(f.name))
)

SELECT
    v.*,

    -- batch label via mapping
    COALESCE(
        NULLIF(TRIM(v.transgene_base_code), ''),
        s.s_base,
        l.l_base
    )::text AS transgene_base_code_filled,

    -- created_by enrichment
    COALESCE(
        NULLIF(TRIM(v.allele_number::text), ''),
        (s.s_num)::text,
        (l.l_num)::text
    )::text AS allele_number_filled,

    -- base code (TEXT): prefer v.*, then sidecar, then link-table
    COALESCE(
        NULLIF(TRIM(v.transgene_name), ''),
        (
            SELECT COALESCE(tg.transgene_name, tg.name, s.s_base)
            FROM public.transgenes AS tg
            WHERE tg.transgene_base_code = COALESCE(s.s_base, l.l_base, NULLIF(TRIM(v.transgene_base_code), ''))
            LIMIT 1
        ),
        COALESCE(s.s_base, l.l_base, NULLIF(TRIM(v.transgene_base_code), ''))
    )::text AS transgene_name_filled,

    -- allele number (TEXT): prefer v.*, then sidecar, then link-table
    COALESCE(
        NULLIF(TRIM(s.s_code), ''),
        NULLIF(TRIM(l.l_code), ''),
        NULLIF(TRIM(l.l_name), ''),
        NULLIF(TRIM(v.allele_number::text), ''),
        (s.s_num)::text,
        (l.l_num)::text
    )::text AS allele_code_filled,

    -- human name (TEXT): prefer v.*, then transgenes.name/transgene_name for chosen base, else base
    (
        CASE
            WHEN
                COALESCE(
                    NULLIF(TRIM(v.transgene_base_code), ''),
                    s.s_base, l.l_base
                ) IS NOT NULL
                AND COALESCE(
                    NULLIF(TRIM(v.allele_number::text), ''),
                    (s.s_num)::text, (l.l_num)::text
                ) IS NOT NULL
                THEN
                    'Tg('
                    || (
                        -- letters + zero-padded trailing digits to 4 places
                        REGEXP_REPLACE(
                            LOWER(COALESCE(NULLIF(TRIM(v.transgene_base_code), ''), s.s_base, l.l_base)), '[0-9]+$', ''
                        )
                        ||
                        LPAD(
                            REGEXP_REPLACE(
                                LOWER(COALESCE(NULLIF(TRIM(v.transgene_base_code), ''), s.s_base, l.l_base)),
                                '^[A-Za-z]+',
                                ''
                            ),
                            4,
                            '0'
                        )
                    ) || ')'
                    || COALESCE(
                        NULLIF(TRIM(s.s_code), ''),
                        NULLIF(TRIM(l.l_code), ''),
                        NULLIF(TRIM(l.l_name), ''),
                        NULLIF(TRIM(v.allele_number::text), ''),
                        (s.s_num)::text,
                        (l.l_num)::text
                    )
        END
    )::text AS transgene_pretty_filled,

    -- NEW: allele_code_filled (prefer code, then name, then number)
    COALESCE(sb.batch_label, fsb.seed_batch_id) AS batch_label,

    -- Pretty: Tg(<lower(base with padded trailing digits to 4)>)<allele_code_or_name_or_number>
    COALESCE(NULLIF(TRIM(v.created_by), ''), NULLIF(TRIM(f.created_by), '')) AS created_by_enriched

FROM public.vw_fish_overview AS v
LEFT JOIN public.fish AS f
    ON UPPER(TRIM(f.fish_code)) = UPPER(TRIM(v.fish_code))
LEFT JOIN public.fish_seed_batches AS fsb ON f.id_uuid = fsb.fish_id
LEFT JOIN public.seed_batches AS sb ON fsb.seed_batch_id = sb.seed_batch_id
LEFT JOIN sidecar AS s ON f.id_uuid = s.fish_id
LEFT JOIN linkx AS l ON f.id_uuid = l.fish_id;
