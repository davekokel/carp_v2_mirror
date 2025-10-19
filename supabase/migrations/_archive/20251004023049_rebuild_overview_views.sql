BEGIN;

-- Base overview: cohorts that actually have genotype links
DROP VIEW IF EXISTS public.v_fish_overview CASCADE;
CREATE VIEW public.v_fish_overview AS
SELECT
    f.id,
    f.fish_code,
    f.name,
    -- base codes
    f.created_at,
    -- allele numbers (as text)
    f.created_by,
    -- allele nicknames (non-empty only)
    (
        SELECT string_agg(base, ', ' ORDER BY base)
        FROM (
            SELECT DISTINCT t.transgene_base_code AS base
            FROM public.fish_transgene_alleles AS t
            WHERE t.fish_id = f.id
        ) AS s1
    ) AS transgene_base_code_filled,
    (
        SELECT string_agg(an, ', ' ORDER BY an)
        FROM (
            SELECT DISTINCT t.allele_number::text AS an
            FROM public.fish_transgene_alleles AS t
            WHERE t.fish_id = f.id
        ) AS s2
    ) AS allele_code_filled,
    (
        SELECT string_agg(nn, ', ' ORDER BY nn)
        FROM (
            SELECT DISTINCT nullif(btrim(t.allele_nickname), '') AS nn
            FROM public.fish_transgene_alleles AS t
            WHERE t.fish_id = f.id
        ) AS s3
        WHERE nn IS NOT NULL
    ) AS allele_name_filled
FROM public.fish AS f
WHERE
    EXISTS (
        SELECT 1 FROM public.fish_transgene_alleles AS t
        WHERE t.fish_id = f.id
    )
ORDER BY f.created_at DESC;

-- Label overlay: keep a stable schema even if extras are absent
DROP VIEW IF EXISTS public.vw_fish_overview_with_label;
CREATE VIEW public.vw_fish_overview_with_label AS
SELECT
    v.*,
    NULL::text AS nickname,
    NULL::text AS line_building_stage,
    NULL::date AS date_birth,
    NULL::text AS batch_label,
    NULL::text AS created_by_enriched,
    NULL::timestamptz AS last_plasmid_injection_at,
    NULL::text AS plasmid_injections_text,
    NULL::timestamptz AS last_rna_injection_at,
    NULL::text AS rna_injections_text
FROM public.v_fish_overview AS v;

COMMIT;
