BEGIN;

-- Base overview: fish that actually have genotype links
DROP VIEW IF EXISTS public.v_fish_overview CASCADE;
CREATE VIEW public.v_fish_overview AS
SELECT
    f.id,
    f.fish_code,
    f.name,
    f.created_at,
    f.created_by,
    (
        SELECT string_agg(DISTINCT t.transgene_base_code, ', ' ORDER BY t.transgene_base_code)
        FROM public.fish_transgene_alleles AS t
        WHERE t.fish_id = f.id
    ) AS transgene_base_code_filled,
    (
        SELECT string_agg(DISTINCT t.allele_number::text, ', ' ORDER BY t.allele_number)
        FROM public.fish_transgene_alleles AS t
        WHERE t.fish_id = f.id
    ) AS allele_code_filled,
    (
        SELECT string_agg(DISTINCT nn, ', ' ORDER BY nn)
        FROM (
            SELECT nullif(btrim(t.allele_nickname), '') AS nn
            FROM public.fish_transgene_alleles AS t
            WHERE t.fish_id = f.id
        ) AS s
        WHERE nn IS NOT NULL
    ) AS allele_name_filled
FROM public.fish AS f
WHERE
    EXISTS (
        SELECT 1 FROM public.fish_transgene_alleles AS t
        WHERE t.fish_id = f.id
    )
ORDER BY f.created_at DESC;

-- Thin label overlay: keeps columns stable even if extras aren’t present yet
DROP VIEW IF EXISTS public.v_fish_overview_with_label;
CREATE VIEW public.v_fish_overview_with_label AS
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
