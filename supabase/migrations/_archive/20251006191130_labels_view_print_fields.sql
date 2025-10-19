DROP VIEW IF EXISTS public.vw_fish_overview_with_label CASCADE;
CREATE VIEW public.vw_fish_overview_with_label AS
WITH last_batch AS (
    SELECT DISTINCT ON (m.fish_id)
        m.fish_id,
        m.seed_batch_id,
        m.logged_at
    FROM public.fish_seed_batches_map AS m
    ORDER BY m.fish_id ASC, m.logged_at DESC NULLS LAST
)

SELECT
    v.*,
    NULL::text AS transgene_base_code_filled,
    NULL::text AS allele_code_filled,
    NULL::text AS allele_name_filled,
    lb.seed_batch_id AS seed_batch_id_latest,
    lb.seed_batch_id AS batch_label,
    NULL::text AS plasmid_injections_text,
    NULL::text AS rna_injections_text,
    f.created_by AS created_by_enriched,
    CASE
        WHEN v.date_birth IS NOT NULL THEN ((CURRENT_DATE - v.date_birth) / 7)::int
        ELSE NULL::int
    END AS age_weeks
FROM public.v_fish_overview_canonical AS v
LEFT JOIN public.fish AS f ON v.fish_code = f.fish_code
LEFT JOIN last_batch AS lb ON f.id_uuid = lb.fish_id;
